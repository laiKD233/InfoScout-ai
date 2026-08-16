"""多源数据抓取器：Reddit / YouTube / 稀土掘金 / 通用 Web / Hacker News / GitHub。

每个模块暴露一个 ``search_<source>(query, count) -> list[dict]``，
返回统一形状的素材 dict：

    {"title", "url", "source", "snippet"}

设计约定：
- 全部走公开 HTTP 接口（RSS / 官方 API），尽量不依赖 API Key；
  需要 Key 的场景由上层 last30days 引擎处理。
- 永不抛异常：任何网络/解析失败返回 []，由调用方降级到其它数据源。
"""
from __future__ import annotations

from app.agents.tools.sources.github import search_github
from app.agents.tools.sources.hackernews import search_hackernews
from app.agents.tools.sources.juejin import search_juejin
from app.agents.tools.sources.reddit import search_reddit
from app.agents.tools.sources.web import search_web
from app.agents.tools.sources.youtube import search_youtube

# 数据源 id -> 抓取函数。retriever 与 MCP server 共用这一张表。
SOURCE_SEARCHERS = {
    "web": search_web,
    "reddit": search_reddit,
    "youtube": search_youtube,
    "juejin": search_juejin,
    "hackernews": search_hackernews,
    "github": search_github,
}

# graph 检索阶段默认启用的数据源（并行调用，任一失败不影响其它）
DEFAULT_SOURCES = ["web", "reddit", "youtube", "juejin", "hackernews", "github"]

__all__ = [
    "search_reddit",
    "search_youtube",
    "search_juejin",
    "search_web",
    "search_hackernews",
    "search_github",
    "SOURCE_SEARCHERS",
    "DEFAULT_SOURCES",
]
