"""
检索 Agent 节点 —— 并行执行（builder 用 Send 按子任务 fan-out）。

每个实例只处理一个子任务：并行调用多个数据源 Tools（web / reddit /
youtube / 稀土掘金），把原始素材追加进共享 State 的 raw_materials
（add reducer 自动合并）。子任务间由 Send 并行、单子任务内多源并行，
两层并行共同压缩检索耗时。

注意：本节点收到的不是全量 ResearchState，而是 Send 传入的载荷
{"subtask": ..., "mock": ..., "days": ..., "sources": ...}。
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.agents.graph.state import Material, make_event
from app.agents.tools.sources import DEFAULT_SOURCES, SOURCE_SEARCHERS

logger = logging.getLogger(__name__)

_PER_TASK_RESULTS = 5


def _search_sources(
    query: str,
    sources: list[str] | None = None,
    count: int = _PER_TASK_RESULTS,
) -> tuple[list[Material], dict[str, int]]:
    """并行调用多个数据源抓取器。

    返回 (materials, per_source)：materials 为统一素材；per_source 记录
    各源实际返回条数（0 = 该源无结果或不可达），供进度展示与空结果诊断。
    """
    sources = sources or DEFAULT_SOURCES
    materials: list[Material] = []
    per_source: dict[str, int] = {}

    def _run(source: str) -> tuple[str, list[dict]]:
        try:
            searcher = SOURCE_SEARCHERS[source]
            return source, searcher(query, count)
        except Exception as e:  # noqa: BLE001
            logger.warning("数据源 %s 检索失败: %s", source, e)
            return source, []

    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures = [pool.submit(_run, s) for s in sources]
        for fut in as_completed(futures):
            source, items = fut.result()
            per_source[source] = len(items)
            materials.extend(
                {
                    "subtask_id": "",  # 由调用方回填
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": source,
                    "snippet": item.get("snippet", ""),
                }
                for item in items
            )

    return materials, per_source


def _mock_materials(subtask: dict) -> list[Material]:
    """mock 模式：返回演示素材，保证无网络/无 Key 也能跑通全图。"""
    return [
        {
            "subtask_id": subtask["id"],
            "title": f"[Mock] {subtask['query']} 相关文章 {i + 1}",
            "url": f"https://example.com/{subtask['id']}/{i + 1}",
            "source": "web",
            "snippet": f"这是关于「{subtask['query']}」的演示摘要 {i + 1}，用于验证图编排链路。",
        }
        for i in range(2)
    ]


def retriever_node(payload: dict[str, Any]) -> dict:
    """检索单个子任务，产出 raw_materials 增量。"""
    subtask = payload["subtask"]
    events = [
        make_event("retriever", "start", f"[{subtask['id']}] 检索：{subtask['query']}")
    ]

    materials: list[Material] = []
    errors: list[str] = []
    counts: dict[str, int] = {}

    if payload.get("mock"):
        materials = _mock_materials(subtask)
        counts = {"web": len(materials)}
    else:
        # 用户勾选的数据源（仅保留本引擎支持的）；空则用全部默认源
        sources = [
            s for s in (payload.get("sources") or []) if s in SOURCE_SEARCHERS
        ] or DEFAULT_SOURCES
        try:
            found, counts = _search_sources(subtask["query"], sources=sources)
            for m in found:
                m["subtask_id"] = subtask["id"]
            materials = found
        except Exception as e:  # noqa: BLE001
            logger.exception("检索失败: %s", subtask["query"])
            errors.append(f"retriever[{subtask['id']}]: {e}")
            events.append(make_event("retriever", "error", f"[{subtask['id']}] {e}"))

    summary = ", ".join(f"{s}:{n}" for s, n in sorted(counts.items())) or "无源"
    events.append(
        make_event(
            "retriever", "done",
            f"[{subtask['id']}] 获得 {len(materials)} 条素材（{summary}）",
        )
    )

    # 空结果时给一条可诊断的错误，让用户知道是"网络不通"还是"主题无结果"
    if not materials and not payload.get("mock"):
        errors.append(
            f"retriever[{subtask['id']}]: 各数据源均无结果（{summary}）。"
            "请确认后端可访问外网，或主题是否为真实存在的话题。"
        )

    return {"raw_materials": materials, "progress_events": events, "errors": errors}
