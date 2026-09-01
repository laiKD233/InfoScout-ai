"""多源数据抓取器：通用 Web（必应中国）/ Reddit / 稀土掘金 / B站 / 思否 / YouTube /
Hacker News / GitHub。

每个模块暴露一个 ``search_<source>(query, count) -> list[dict]``，
返回统一形状的素材 dict：

    {"title", "url", "source", "snippet"}

设计约定：
- 图引擎默认源为**纯境内可达**的国内源（web=必应中国、juejin、bilibili、segmentfault），
  因为所在部署环境通常无法访问国外被墙服务；国外源（reddit/youtube/hackernews/github）
  被需要外网的 CLI 引擎保留使用。
- 全部走公开 HTTP 接口（RSS / 官方 API），尽量不依赖 API Key；
  需要 Key 的场景由上层 last30days 引擎处理。
- 永不抛异常：任何网络/解析失败返回 []，由调用方降级到其它数据源。
"""
from __future__ import annotations

from app.agents.tools.sources.bilibili import search_bilibili
from app.agents.tools.sources.github import search_github
from app.agents.tools.sources.hackernews import search_hackernews
from app.agents.tools.sources.juejin import search_juejin
from app.agents.tools.sources.reddit import search_reddit
from app.agents.tools.sources.segmentfault import search_segmentfault
from app.agents.tools.sources.web import search_web
from app.agents.tools.sources.youtube import search_youtube

# 数据源 id -> 抓取函数。retriever 与 MCP server 共用这一张表。
SOURCE_SEARCHERS = {
    "web": search_web,            # 必应中国（境内可达，可搜中文+英文）
    "reddit": search_reddit,      # 外网源；仅 CLI 引擎在有外网的机器上用
    "youtube": search_youtube,    # 外网源；仅 CLI 引擎在有外网的机器上用
    "juejin": search_juejin,      # 稀土掘金（境内）
    "hackernews": search_hackernews,  # 外网源
    "github": search_github,      # 外网源
    "bilibili": search_bilibili,  # B站（境内）
    "segmentfault": search_segmentfault,  # 思否社区（境内）
}

# graph 检索阶段默认启用的数据源（并行调用，任一失败不影响其它）。
# 全部为境内网络可达的源，确保纯国内环境也能跑通全图。
DEFAULT_SOURCES = ["web", "juejin", "bilibili", "segmentfault"]

__all__ = [
    "search_reddit",
    "search_youtube",
    "search_juejin",
    "search_web",
    "search_hackernews",
    "search_github",
    "search_bilibili",
    "search_segmentfault",
    "SOURCE_SEARCHERS",
    "DEFAULT_SOURCES",
]