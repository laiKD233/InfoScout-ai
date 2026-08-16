"""
多源数据源 Tools —— Function Calling 封装（LangChain @tool）。

把 Reddit / YouTube / 稀土掘金 / 通用 Web / Hacker News / GitHub 六个数据源封装成 LangChain Tool，
@tool 装饰器从函数签名 + docstring 自动生成 Function Calling 的 JSON schema。
同一批函数另经 app/mcp_server.py 以 MCP 方式暴露给外部 Agent。

用途：
- graph 的检索节点通过 SOURCE_SEARCHERS 直接并行调用底层抓取器（确定性检索）；
- chat 的 ReAct Agent 通过 Function Calling 自主决定是否调用这些工具（见 research_agent）。
"""
from __future__ import annotations

import json

from langchain_core.tools import tool

from app.agents.tools.sources import (
    search_github,
    search_hackernews,
    search_juejin,
    search_reddit,
    search_web,
    search_youtube,
)


def _dump(items: list[dict]) -> str:
    """把素材列表转成 Agent 可读的 JSON 字符串。"""
    return json.dumps(items, ensure_ascii=False)


@tool
def search_reddit(query: str, count: int = 5) -> str:
    """在 Reddit 上检索主题相关讨论，返回帖子列表（JSON）。

    适合获取真实用户口碑、争议与社区热度。免 API Key（走公开 RSS）。

    Args:
        query: 检索关键词。
        count: 返回条数，默认 5。
    """
    return _dump(search_reddit(query, count))


@tool
def search_youtube(query: str, count: int = 5) -> str:
    """在 YouTube 上检索主题相关视频，返回视频列表（JSON）。

    适合获取视频测评、教程与观点。免 API Key（走官方 feeds）。

    Args:
        query: 检索关键词。
        count: 返回条数，默认 5。
    """
    return _dump(search_youtube(query, count))


@tool
def search_juejin(query: str, count: int = 5) -> str:
    """在稀土掘金（juejin.cn）上检索主题相关文章，返回文章列表（JSON）。

    适合获取中文技术社区的观点、教程与实践经验。

    Args:
        query: 检索关键词。
        count: 返回条数，默认 5。
    """
    return _dump(search_juejin(query, count))


@tool
def search_hackernews(query: str, count: int = 5) -> str:
    """在 Hacker News 上检索主题相关讨论/文章，返回列表（JSON）。

    适合获取技术圈的最新动态与观点（免 Key，走官方 Algolia API）。

    Args:
        query: 检索关键词。
        count: 返回条数，默认 5。
    """
    return _dump(search_hackernews(query, count))


@tool
def search_github(query: str, count: int = 5) -> str:
    """在 GitHub 上检索主题相关仓库，返回仓库列表（JSON）。

    适合获取开源项目、star 数、项目活跃度（免 Key，走官方搜索 API）。

    Args:
        query: 检索关键词。
        count: 返回条数，默认 5。
    """
    return _dump(search_github(query, count))


@tool
def search_web(query: str, count: int = 5) -> str:
    """通用网页检索（DuckDuckGo，免 Key），返回网页结果列表（JSON）。

    兜底数据源：当其它垂直源结果不足时补充通用网络信息。

    Args:
        query: 检索关键词。
        count: 返回条数，默认 5。
    """
    return _dump(search_web(query, count))


# Function Calling 工具集合（chat Agent 可用）
MULTI_SOURCE_TOOLS = [
    search_reddit,
    search_youtube,
    search_juejin,
    search_hackernews,
    search_github,
    search_web,
]
