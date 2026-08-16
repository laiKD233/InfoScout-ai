"""
清洗 Agent 节点 —— 并行执行（builder 用 Send 按子任务 fan-out）。

对单个子任务的原始素材做内容清洗：去噪去重、提炼要点、按主题相关度
打分过滤（<0.3 丢弃）。用 fast 档模型（批量小任务，控成本）。

Send 载荷：{"subtask": ..., "materials": [...], "topic": ..., "mock": ...}
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents.graph.nodes.common import parse_json_block
from app.agents.graph.state import Material, make_event
from app.core.llm import get_llm

logger = logging.getLogger(__name__)

_PROMPT = """你是信息清洗专家。以下是关于调研主题「{topic}」的原始检索素材（子任务角度：{angle}）。

请对每条素材：
1. 提炼 content：1-2 句核心要点（去掉广告、导航文本等噪音）
2. 打 relevance 分：与调研主题的相关度 0-1（无关广告/推销页给 0）

原始素材：
{materials}

只输出 JSON 数组，元素形如 {{"index": 0, "content": "要点", "relevance": 0.8}}，
与输入素材按 index 对应，不要输出其他内容。"""

_MIN_RELEVANCE = 0.3


def _format_materials(materials: list[Material]) -> str:
    lines = []
    for i, m in enumerate(materials):
        lines.append(f"[{i}] 标题: {m.get('title', '')}\n    摘要: {m.get('snippet', '')[:300]}")
    return "\n".join(lines)


def cleaner_node(payload: dict[str, Any]) -> dict:
    """清洗单个子任务的素材，产出 cleaned_materials 增量。"""
    subtask = payload["subtask"]
    materials: list[Material] = payload.get("materials", [])
    events = [
        make_event("cleaner", "start", f"[{subtask['id']}] 清洗 {len(materials)} 条素材")
    ]

    if not materials:
        events.append(make_event("cleaner", "done", f"[{subtask['id']}] 无素材可清洗"))
        return {"cleaned_materials": [], "progress_events": events}

    cleaned: list[Material] = []
    errors: list[str] = []

    llm = None if payload.get("mock") else get_llm("fast")
    if llm is not None:
        try:
            resp = llm.invoke(
                _PROMPT.format(
                    topic=payload.get("topic", ""),
                    angle=subtask.get("angle", ""),
                    materials=_format_materials(materials),
                )
            )
            parsed = parse_json_block(getattr(resp, "content", ""))
            if isinstance(parsed, list):
                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    idx = item.get("index")
                    rel = float(item.get("relevance", 0))
                    if isinstance(idx, int) and 0 <= idx < len(materials) and rel >= _MIN_RELEVANCE:
                        m = dict(materials[idx])
                        m["content"] = str(item.get("content", m.get("snippet", "")))
                        m["relevance"] = rel
                        cleaned.append(m)  # type: ignore[arg-type]
        except Exception as e:  # noqa: BLE001
            logger.exception("cleaner LLM 调用失败，走透传降级")
            errors.append(f"cleaner[{subtask['id']}]: {e}")
            events.append(make_event("cleaner", "error", f"[{subtask['id']}] {e}"))

    if not cleaned:
        # 降级/mock：直接透传 snippet 当作 content，给默认相关度
        for m in materials:
            mm = dict(m)
            mm["content"] = m.get("snippet", "")
            mm["relevance"] = 0.5
            cleaned.append(mm)  # type: ignore[arg-type]

    events.append(
        make_event(
            "cleaner", "done",
            f"[{subtask['id']}] 保留 {len(cleaned)}/{len(materials)} 条有效素材",
        )
    )
    return {"cleaned_materials": cleaned, "progress_events": events, "errors": errors}
