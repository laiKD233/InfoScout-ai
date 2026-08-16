"""节点公共工具：LLM JSON 输出的稳健解析。"""
from __future__ import annotations

import json
import re
from typing import Any


def parse_json_block(text: str) -> Any:
    """从 LLM 回复中提取 JSON（容忍 ```json 围栏、前后废话）。失败返回 None。"""
    if not text:
        return None
    # 优先取代码围栏内的内容
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    candidate = fence.group(1) if fence else text
    # 定位第一个 { 或 [ 到最后一个 } 或 ]
    start = min(
        (i for i in (candidate.find("{"), candidate.find("[")) if i >= 0),
        default=-1,
    )
    if start < 0:
        return None
    end = max(candidate.rfind("}"), candidate.rfind("]"))
    if end <= start:
        return None
    try:
        return json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return None
