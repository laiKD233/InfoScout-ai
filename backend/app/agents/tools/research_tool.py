"""
调研工具：触发 last30days CLI 做全网调研。

LangChain Tool 的本质：一个带描述的函数，Agent 可以决定是否调用它。
@tool 装饰器自动从函数签名 + docstring 生成工具 schema（对应 Function Calling 的 JSON schema）。
"""
from __future__ import annotations

from langchain_core.tools import tool

from app.services.research_service import run_research_sync


@tool
def research_topic(topic: str) -> str:
    """对指定主题进行全网调研（Reddit/X/HN/GitHub/arXiv 等多平台），返回调研报告。

    当用户问题需要最新信息、外部数据或你无法直接回答时调用此工具。
    返回的是 markdown 格式的研究简报，包含来源链接。

    Args:
        topic: 调研主题，应为简洁的关键词或短语，如 "Claude Code" 或 "AI agent 框架对比"。
    """
    return run_research_sync(topic, mock=True)
