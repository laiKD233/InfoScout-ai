"""通用 Web 检索源（免 Key）：DuckDuckGo HTML 端点，标准库实现。"""
from __future__ import annotations

import logging
import re

from app.agents.tools.sources.common import (
    http_get,
    make_item,
    safe_quote,
    strip_html,
)

logger = logging.getLogger(__name__)

_DDG_URL = "https://html.duckduckgo.com/html/?q={query}"

_RESULT_A_RE = re.compile(
    r'class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_SNIPPET_RE = re.compile(
    r'class="result__snippet"[^>]*>(?P<snippet>.*?)</(?:a|div)>',
    re.IGNORECASE | re.DOTALL,
)


def _unwrap_ddg_redirect(href: str) -> str:
    """DuckDuckGo 用 //duckduckgo.com/l/?uddg=<encoded> 包一层跳转，需还原。"""
    if "uddg=" not in href:
        if href.startswith("//"):
            return f"https:{href}"
        return href
    from urllib.parse import parse_qs, urlparse

    try:
        parsed = urlparse(href if href.startswith("http") else f"https:{href}")
        return parse_qs(parsed.query).get("uddg", [href])[0]
    except (ValueError, AttributeError):
        return href


def search_web(query: str, count: int = 5) -> list[dict]:
    """通用 Web 检索，返回统一素材列表；失败返回 []。"""
    try:
        html_text = http_get(_DDG_URL.format(query=safe_quote(query)))
    except Exception as e:  # noqa: BLE001
        logger.warning("Web 检索失败: %s", e)
        return []

    titles = _RESULT_A_RE.findall(html_text)
    snippets = _SNIPPET_RE.findall(html_text)

    items: list[dict] = []
    for i, (href, title) in enumerate(titles[:count]):
        url = _unwrap_ddg_redirect(href)
        snippet = strip_html(snippets[i]) if i < len(snippets) else ""
        items.append(make_item(title, url, "web", snippet))
    return items
