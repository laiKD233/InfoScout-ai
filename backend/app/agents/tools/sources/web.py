"""通用 Web 检索源（免 Key）：必应中国搜索，标准库实现。

改为必应中国（cn.bing.com）以适配纯境内网络——国外端（DuckDuckGo、
Google 等）在国内不可达。必应中国既能搜到中文内容，也能搜到英文外网内容，
解析稳定的 <li class="b_algo"> 结果块。失败返回 []（由上层降级到其它源）。
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

from app.agents.tools.sources.common import (
    http_get,
    make_item,
    strip_html,
)

logger = logging.getLogger(__name__)

_BING_URL = "https://cn.bing.com/search?q={query}&setlang=zh-hans"

# 结果块（b_algo）内的标题 <h2 ...>
_H2_RE = re.compile(r'<h2[^>]*>(.*?)</h2>', re.S)
# 标题内的目标链接（attrs 顺序不固定：href 总在 a 标签上）
_HREF_RE = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
# 摘要段落：取块内第一个 <p> 文本
_P_RE = re.compile(r'<p[^>]*>(.*?)</p>', re.S)


def _parse_bing(html_text: str, count: int) -> list[dict]:
    """按 b_algo 块切分，逐块提取标题链接与摘要。"""
    items: list[dict] = []
    for block in re.split(r'<li class="b_algo"', html_text)[1:]:
        if len(items) >= count:
            break
        h2 = _H2_RE.search(block)
        if not h2:
            continue
        href_match = _HREF_RE.search(h2.group(1))
        if not href_match:
            continue
        title = strip_html(href_match.group(2))
        if not title:
            continue
        # 摘要：取块内第一个 <p> 文本
        p_match = _P_RE.search(block)
        snippet = strip_html(p_match.group(1)) if p_match else ""
        items.append(make_item(title, href_match.group(1), "web", snippet))
    return items


def search_web(query: str, count: int = 5) -> list[dict]:
    """通用 Web 检索（必应中国），返回统一素材列表；失败返回 []。"""
    try:
        html_text = http_get(_BING_URL.format(query=quote(query)))
        return _parse_bing(html_text, count)
    except Exception as e:  # noqa: BLE001
        logger.warning("Web 检索失败: %s", e)
        return []