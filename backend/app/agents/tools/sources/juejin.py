"""稀土掘金（Juejin）检索源：公开 search API（免登录）。"""
from __future__ import annotations

import logging

from app.agents.tools.sources.common import http_post_json, make_item, strip_html

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://api.juejin.cn/search_api/v1/search"
_POST_URL = "https://juejin.cn/post/{article_id}"


def search_juejin(query: str, count: int = 5) -> list[dict]:
    """检索稀土掘金文章，返回统一素材列表；失败返回 []。"""
    try:
        payload = {
            "key_word": query,
            "query": query,  # 不同版本 API 字段名不一致，同时带上
            "id_type": 0,
            "cursor": "0",
            "limit": max(count, 1),
            "sort_type": 0,
            "search_type": 0,
        }
        data = http_post_json(
            _SEARCH_URL,
            payload,
            extra_headers={"Referer": "https://juejin.cn/"},
        )
        raw = data.get("data") or []
        if isinstance(raw, dict):
            raw = raw.get("data") or raw.get("list") or []

        items: list[dict] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            # 搜索结果里文章信息嵌套在 result_model.article_info
            model = entry.get("result_model") or entry.get("article_info") or {}
            info = model.get("article_info") or model if isinstance(model, dict) else {}
            article_id = info.get("article_id") or entry.get("article_id")
            title = info.get("title") or entry.get("title")
            brief = info.get("brief_content") or entry.get("brief_content") or ""
            if not article_id or not title:
                continue
            url = _POST_URL.format(article_id=article_id)
            items.append(make_item(title, url, "juejin", strip_html(brief)))
        return items[:count]
    except Exception as e:  # noqa: BLE001
        logger.warning("稀土掘金检索失败: %s", e)
        return []
