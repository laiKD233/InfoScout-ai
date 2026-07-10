"""
LangChain Agent：智能调研问答助手。

工作流（ReAct 模式）：
1. 用户提问
2. Agent 决定调用哪个工具：
   - search_history_research：先查历史调研（RAG）
   - research_topic：发起新调研
3. 根据工具返回的证据生成中文回答

对应 SpringBoot 里没有的概念——这是 AI 应用的核心编排层。
"""
from __future__ import annotations

import logging

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.agents.tools.research_tool import research_topic
from app.agents.tools.retrieval_tool import search_history_research
from app.core.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个智能调研助手 InfoScout。你的职责是基于全网调研结果回答用户问题。

你可以使用以下工具：
- search_history_research: 检索历史调研结果。**优先**调用此工具，看问题是否已有调研覆盖。
- research_topic: 发起新的全网调研。仅当历史检索无结果，或用户明确要求最新信息时使用。

工作原则：
1. 先尝试 search_history_research，命中则直接基于结果回答。
2. 未命中或结果不足时，调用 research_topic 发起新调研。
3. 回答必须基于工具返回的证据，给出来源链接，不要编造。
4. 用中文回答，条理清晰。
"""


def get_agent_executor() -> AgentExecutor | None:
    """构建 AgentExecutor。无 OPENAI_API_KEY 时返回 None，调用方应降级处理。"""
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY 未配置，Agent 功能不可用")
        return None

    llm_kwargs = {"model": settings.llm_model, "api_key": settings.openai_api_key, "temperature": 0}
    if settings.openai_base_url:
        llm_kwargs["base_url"] = settings.openai_base_url
    llm = ChatOpenAI(**llm_kwargs)

    tools = [search_history_research, research_topic]

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=5)
