"""YouTube 检索源（免 Key）：用官方 feeds/videos.xml 的 Atom 搜索接口。"""
from __future__ import annotations

import logging

from app.agents.tools.sources.common import (
    http_get,
    make_item,
    parse_atom_entries,
    safe_quote,
)

logger = logging.getLogger(__name__)

_FEED_URL = "https://www.youtube.com/feeds/videos.xml?q={query}"


def search_youtube(query: str, count: int = 5) -> list[dict]:
    """检索 YouTube，返回统一素材列表；失败返回 []。"""
    try:
        url = _FEED_URL.format(query=safe_quote(query))
        xml_text = http_get(url)
        items: list[dict] = []
        for e in parse_atom_entries(xml_text):
            if not e.get("title") or not e.get("link"):
                continue
            items.append(make_item(e["title"], e["link"], "youtube", e.get("content", "")))
        return items[:count]
    except Exception as e:  # noqa: BLE001
        logger.warning("YouTube 检索失败: %s", e)
        return []
