"""GitHub 检索源（免 Key）：官方仓库搜索 API，稳定。"""
from __future__ import annotations

import json
import logging

from app.agents.tools.sources.common import http_get, make_item, safe_quote

logger = logging.getLogger(__name__)

_SEARCH_URL = (
    "https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={count}"
)


def search_github(query: str, count: int = 5) -> list[dict]:
    """检索 GitHub 上主题相关仓库，返回统一素材列表；失败返回 []。"""
    try:
        url = _SEARCH_URL.format(query=safe_quote(query), count=count)
        data = json.loads(http_get(url, timeout=15))
        raw = data.get("items") or []

        items: list[dict] = []
        for r in raw:
            if not isinstance(r, dict):
                continue
            full_name = (r.get("full_name") or "").strip()
            html_url = r.get("html_url") or ""
            if not full_name:
                continue
            stars = r.get("stargazers_count") or 0
            desc = (r.get("description") or "").strip()
            snippet = f"⭐ {stars} · {desc}"
            items.append(make_item(full_name, html_url, "github", snippet))
        return items[:count]
    except Exception as e:  # noqa: BLE001
        logger.warning("GitHub 检索失败: %s", e)
        return []
