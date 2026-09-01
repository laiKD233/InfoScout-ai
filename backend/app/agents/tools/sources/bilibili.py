"""B站（哔哩哔哩）检索源（免 Key）：国内主流视频平台。

B站在境内网络可达，作为图引擎的视频观点数据源（对标 YouTube 的角色）。
解析 bili-video-card 卡片块提取视频链接与标题。失败返回 []（由上层降级）。
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

_SEARCH_URL = "https://search.bilibili.com/all?keyword={query}"

# B站搜索页是 SSR HTML：每个视频卡片含
#   <a href="//www.bilibili.com/video/.." ... target="_blank"><div class="bili-video-card__image">...
#      <h3 class="bili-video-card__info--tit" title="实际标题">
# 因此 href（视频链接）与 title（标题文本）全局按卡片顺序一一对应。
_VIDEO_HREF_RE = re.compile(r'href="(//www\.bilibili\.com/video/[^"]+)"', re.I)
_TITLE_RE = re.compile(r'class="bili-video-card__info--tit"[^>]*title="([^"]+)"')


def _parse_bili(html_text: str, count: int) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for href, title in zip(
        _VIDEO_HREF_RE.findall(html_text), _TITLE_RE.findall(html_text)
    ):
        if len(items) >= count:
            break
        url = "https:" + href
        title = strip_html(title)
        if not title or url in seen:
            continue
        seen.add(url)
        items.append(make_item(title, url, "bilibili"))
    return items


def search_bilibili(query: str, count: int = 5) -> list[dict]:
    """检索 B站视频，返回统一素材列表；失败返回 []。"""
    try:
        html_text = http_get(_SEARCH_URL.format(query=safe_quote(query)))
        return _parse_bili(html_text, count)
    except Exception as e:  # noqa: BLE001
        logger.warning("B站检索失败: %s", e)
        return []