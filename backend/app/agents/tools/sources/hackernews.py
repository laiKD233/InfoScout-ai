"""Hacker News 检索源（免 Key）：官方 Algolia Search API，稳定无鉴权。"""
from __future__ import annotations

import json
import logging

from app.agents.tools.sources.common import http_get, make_item, safe_quote

logger = logging.getLogger(__name__)

_ALGOLIA_URL = (
    "https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage={count}"
)
_ITEM_URL = "https://news.ycombinator.com/item?id={object_id}"


def search_hackernews(query: str, count: int = 5) -> list[dict]:
    """检索 Hacker News 上的相关讨论/文章，返回统一素材列表；失败返回 []。"""
    try:
        url = _ALGOLIA_URL.format(query=safe_quote(query), count=count)
        data = json.loads(http_get(url))
        hits = data.get("hits") or []

        items: list[dict] = []
        for h in hits:
            if not isinstance(h, dict):
                continue
            title = (h.get("title") or "").strip()
            if not title:
                continue
            link = h.get("url") or _ITEM_URL.format(object_id=h.get("objectID", ""))
            points = h.get("points") or 0
            comments = h.get("num_comments") or 0
            text = (h.get("story_text") or "").strip()[:200]
            meta = f"{points} 分 · {comments} 评论"
            snippet = f"{meta}\n{text}" if text else meta
            items.append(make_item(title, link, "hackernews", snippet))
        return items[:count]
    except Exception as e:  # noqa: BLE001
        logger.warning("Hacker News 检索失败: %s", e)
        return []
