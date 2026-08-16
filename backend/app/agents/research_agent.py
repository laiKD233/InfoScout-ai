"""
调研 Agent：LangChain ReAct Agent，能自主决定调用调研工具还是检索历史。

对应 SpringBoot 里没有的概念——这是 AI 应用特有的"编排层"。
Agent = LLM + Tools，LLM 根据用户问题决定调用哪个工具、传什么参数、
要不要多步推理，而不是写死的 if/else 流程。
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents.tools.research_tool import research_topic
from app.agents.tools.retrieval_tool import search_history_research
from app.agents.tools.source_tools import MULTI_SOURCE_TOOLS
from app.core.llm import get_llm
from app.services.research_service import run_research_sync

logger = logging.getLogger(__name__)

# 工具列表：Agent 能感知到的全部能力（高层调研 + 历史检索 + 多源直查）
TOOLS = [research_topic, search_history_research, *MULTI_SOURCE_TOOLS]

SYSTEM_PROMPT = """你是 InfoScout AI，一个全网智能调研助手。

你的能力（通过 Function Calling 自主选择调用）：
1. research_topic：对任意主题发起全网调研（覆盖 Reddit/X/HN/GitHub/arXiv 等平台）
2. search_history_research：检索历史调研结果（Milvus + BGE-Reranker），避免重复调研
3. search_reddit / search_youtube / search_juejin / search_web：定向检索单一数据源

决策原则：
- 用户问题涉及最新动态、外部信息、或你无法直接回答时，先尝试 search_history_research
- 若历史结果不足，需要综合多方信息时调用 research_topic；只需单一来源时用对应源工具
- 调研完成后，基于返回的报告用中文给出结构化总结，包含关键发现和来源链接
- 简单问候或闲聊无需调用工具，直接回答
"""


def _build_agent():
    """构建 LangChain Agent。返回 (agent, tools) 或 (None, [])。

    用 get_llm("smart") 取模型：配了 OpenAI 走 OpenAI，只配 DeepSeek 时
    回落到 DeepSeek，保证 /chat 与图引擎共用同一套"多模型分工"逻辑。
    """
    llm = get_llm("smart")
    if llm is None:
        return None, []

    # create_react_agent 是 LangGraph 提供的 ReAct 模式实现（推理-行动循环）
    from langgraph.prebuilt import create_react_agent

    agent = create_react_agent(llm, TOOLS, prompt=SYSTEM_PROMPT)
    return agent, TOOLS


def run_agent(question: str) -> dict[str, Any]:
    """同步运行 Agent。返回 {answer, tools_used, error}。

    无 API Key 时降级为直接调用调研工具，保证演示可用。
    """
    agent, tools = _build_agent()

    if agent is None:
        # 降级路径：无 LLM 时直接跑调研，把结果当作"回答"
        logger.info("未配置 OPENAI_API_KEY，Agent 降级为直接调研")
        report = run_research_sync(question, mock=True)
        return {
            "answer": report[:6000] if report else "调研未返回内容",
            "tools_used": ["research_topic (降级模式)"],
            "error": None,
        }

    try:
        result = agent.invoke({"messages": [("user", question)]})
        # 提取最后一条 AI 消息作为回答
        messages = result.get("messages", [])
        answer = ""
        for msg in reversed(messages):
            content = getattr(msg, "content", "")
            if content and getattr(msg, "type", "") == "ai":
                answer = content
                break

        # 统计实际调用了哪些工具
        tools_used = sorted(
            {getattr(m, "name", "") for m in messages if getattr(m, "type", "") == "tool"}
        )
        tools_used = [t for t in tools_used if t]

        return {"answer": answer, "tools_used": tools_used, "error": None}
    except Exception as e:  # noqa: BLE001
        logger.exception("Agent 执行失败")
        return {"answer": "", "tools_used": [], "error": str(e)}
