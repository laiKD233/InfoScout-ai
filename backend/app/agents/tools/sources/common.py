"""多源抓取器的公共工具：HTTP 请求 + 结果归一化（仅用标准库）。"""
from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 InfoScoutAI/2.0"
)
DEFAULT_TIMEOUT = 10

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """去掉 HTML 标签并反转义。"""
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def http_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """GET 并返回文本；失败抛异常（由上层捕获）。"""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_post_json(
    url: str,
    payload: dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """POST JSON 并解析为 dict；失败抛异常。"""
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def make_item(title: str, url: str, source: str, snippet: str = "") -> dict:
    """归一化为统一素材结构。"""
    return {
        "title": strip_html(title) or "(无标题)",
        "url": url,
        "source": source,
        "snippet": strip_html(snippet),
    }


def safe_quote(query: str) -> str:
    return urllib.parse.quote(query)


# ---------------------------------------------------------------------------
# 通用 Atom(RSS) 解析：Reddit / YouTube 搜索源都是 Atom 格式
# ---------------------------------------------------------------------------
def _local(tag: str) -> str:
    """忽略命名空间，取本地标签名（如 {ns}title -> title）。"""
    return tag.rsplit("}", 1)[-1]


def parse_atom_entries(xml_text: str) -> list[dict[str, str]]:
    """解析 Atom feed，返回 [{"title","link","content","author"}]。

    字段名兼容 Reddit（content/author）与 YouTube（media:description）。
    """
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_text)
    entries: list[dict[str, str]] = []
    for entry in root.iter():
        if _local(entry.tag) != "entry":
            continue
        item: dict[str, str] = {"title": "", "link": "", "content": "", "author": ""}
        for child in entry.iter():
            tag = _local(child.tag)
            text = (child.text or "").strip()
            if tag == "title" and not item["title"]:
                item["title"] = text
            elif tag == "link":
                href = child.get("href", "")
                if href and (not item["link"] or "youtube.com" not in item["link"]):
                    item["link"] = href
            elif tag in ("content", "description") and not item["content"]:
                item["content"] = text
            elif tag == "name" and not item["author"]:
                item["author"] = text
        entries.append(item)
    return entries
