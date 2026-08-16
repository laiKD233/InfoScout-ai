"""Reddit 检索源（免 Key）：用 search.rss 的公开 Atom 接口。"""
from __future__ import annotations

import logging

from app.agents.tools.sources.common import (
    http_get,
    make_item,
    parse_atom_entries,
    safe_quote,
)

logger = logging.getLogger(__name__)

_RSS_URL = "https://www.reddit.com/search.rss?q={query}&limit={count}&sort=relevance&restrict_sr=off"


def search_reddit(query: str, count: int = 5) -> list[dict]:
    """检索 Reddit，返回统一素材列表；失败返回 []。"""
    try:
        url = _RSS_URL.format(query=safe_quote(query), count=count)
        xml_text = http_get(url)
        items: list[dict] = []
        for e in parse_atom_entries(xml_text):
            if not e.get("title") or not e.get("link"):
                continue
            snippet = e.get("content", "") or ""
            # 附上作者与子版块，增强素材信息量
            author = e.get("author", "")
            meta = f"r/reddit · {author}" if author else "r/reddit"
            items.append(make_item(e["title"], e["link"], "reddit", f"{meta}\n{snippet}"))
        return items[:count]
    except Exception as e:  # noqa: BLE001
        logger.warning("Reddit 检索失败: %s", e)
        return []
