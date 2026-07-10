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
from app.core.config import get_settings
from app.services.research_service import run_research_sync

logger = logging.getLogger(__name__)

# 工具列表：Agent 能感知到的全部能力
TOOLS = [research_topic, search_history_research]

SYSTEM_PROMPT = """你是 InfoScout AI，一个全网智能调研助手。

你的能力：
1. 调用 research_topic 工具对任意主题发起全网调研（覆盖 Reddit/X/HN/GitHub/arXiv 等平台）
2. 调用 search_history_research 工具检索历史调研结果，避免重复调研

决策原则：
- 用户问题涉及最新动态、外部信息、或你无法直接回答时，先尝试 search_history_research
- 若历史结果不足或无相关结果，再调用 research_topic 发起新调研
- 调研完成后，基于返回的报告用中文给出结构化总结，包含关键发现和来源链接
- 简单问候或闲聊无需调用工具，直接回答
"""


def _build_agent():
    """构建 LangChain Agent。返回 (agent, tools) 或 (None, [])。"""
    settings = get_settings()
    if not settings.openai_api_key:
        return None, []

    from langchain_openai import ChatOpenAI

    llm_kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "api_key": settings.openai_api_key,
        "temperature": 0.3,
    }
    if settings.openai_base_url:
        llm_kwargs["base_url"] = settings.openai_base_url
    llm = ChatOpenAI(**llm_kwargs)

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
