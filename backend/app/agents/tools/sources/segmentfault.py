"""思否（SegmentFault）检索源（免 Key）：中文技术问答社区搜索。

思否是中国本土的中文技术问答社区（技术博客 + 问答），在境内网络可达、
无验证码，适合作为图引擎的"中文社区讨论"数据源（对标 Reddit 的角色）。
失败返回 []（由上层降级到其它源）。
"""
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

_SEARCH_URL = "https://segmentfault.com/search?q={query}"

# 搜索命中区：<h4 ...> 或 .search-result h4 里的文章链接 + 标题
_ITEM_LINK_RE = re.compile(r'<a[^>]*href="(/a/\d+)"[^>]*>(.*?)</a>', re.S)


def _parse_sf(html_text: str, count: int) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for href, title in _ITEM_LINK_RE.findall(html_text):
        if len(items) >= count:
            break
        title_text = re.sub(r"\s+", " ", strip_html(title)).strip()
        if not title_text or href in seen:
            continue
        seen.add(href)
        items.append(
            make_item(title_text, "https://segmentfault.com" + href, "segmentfault")
        )
    return items


def search_segmentfault(query: str, count: int = 5) -> list[dict]:
    """检索思否文章，返回统一素材列表；失败返回 []。"""
    try:
        html_text = http_get(_SEARCH_URL.format(query=safe_quote(query)))
        return _parse_sf(html_text, count)
    except Exception as e:  # noqa: BLE001
        logger.warning("思否检索失败: %s", e)
        return []