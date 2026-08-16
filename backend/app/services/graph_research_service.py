"""
Graph 调研服务：驱动 LangGraph 多 Agent 研究图（多 Agent 编排引擎）。

与 research_service（子进程调 CLI 的旧引擎）并存：
- /api/v1/research        → 旧 CLI 引擎（保留做耗时对比基线）
- /api/v1/research/graph  → 本服务（planner + 检索/清洗并行 + 分析/写作串行）
- /api/v1/research/{id}/stream → SSE 实时进度（progress broker）

图节点是同步阻塞的（LLM/HTTP 调用），statefully 跑在线程池里，
不阻塞 FastAPI 事件循环。执行期间用 graph.stream(stream_mode="values")
逐超步产出完整 State，把进度事件实时 publish 给 SSE。
"""
from __future__ import annotations

import asyncio
import logging

from app.agents.graph.builder import get_research_graph
from app.agents.graph.state import initial_state
from app.core.llm import llm_available
from app.schemas.research import ResearchRequest
from app.services.progress_broker import ProgressBroker, get_progress_broker
from app.services.task_store import TaskStore

logger = logging.getLogger(__name__)

# 单次图执行的整体超时（秒）。目标是"10 分钟内出报告"，留全量余量
GRAPH_TIMEOUT = 600


def _parse_sources(raw: str | None) -> list[str]:
    """把逗号分隔的数据源字符串解析为去重列表。"""
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def _run_graph_stream(
    task_id: str,
    topic: str,
    days: int,
    mock: bool,
    sources: list[str],
    broker: ProgressBroker,
) -> dict:
    """同步执行研究图并实时发布进度；返回最终 State（dict）。

    用 stream_mode="values"：每个超步产出一份完整 State，progress_events
    经 add reducer 累积，按已发布数量差出增量并 publish。

    注意：mock 只由用户显式勾选决定。未配置 LLM Key 时，检索仍走真实抓取，
    仅 planner/cleaner/analyst/writer 的 LLM 步骤降级为规则/模板。
    """
    if not llm_available():
        logger.info("未配置任何 LLM Key：LLM 步骤降级为规则/模板，检索仍为真实抓取")

    graph = get_research_graph()
    state = initial_state(topic, days=days, mock=mock, sources=sources)

    seen = 0
    final_state: dict = state
    for chunk in graph.stream(state, stream_mode="values"):
        final_state = chunk
        events = chunk.get("progress_events", []) or []
        if len(events) > seen:
            for ev in events[seen:]:
                broker.publish(task_id, {"type": "progress", "event": ev})
            seen = len(events)

    return final_state


async def run_graph_research_async(
    task_id: str, req: ResearchRequest, store: TaskStore
) -> None:
    """异步执行 graph 调研任务（HTTP 路由用），全程通过 broker 推进度。"""
    store.update(task_id, status="running", engine="graph")
    broker = get_progress_broker()
    broker.open(task_id)

    sources = _parse_sources(req.sources)
    try:
        final_state = await asyncio.wait_for(
            asyncio.to_thread(
                _run_graph_stream, task_id, req.topic, req.days, req.mock, sources, broker
            ),
            timeout=GRAPH_TIMEOUT,
        )
    except asyncio.TimeoutError:
        store.update(
            task_id,
            status="failed",
            error=f"graph 调研超时（{GRAPH_TIMEOUT}秒）",
        )
        broker.publish(task_id, {"type": "error", "detail": "graph 调研超时"})
        broker.close(task_id)
        return
    except Exception as e:  # noqa: BLE001
        logger.exception("graph 调研失败: %s", req.topic)
        store.update(task_id, status="failed", error=str(e))
        broker.publish(task_id, {"type": "error", "detail": str(e)})
        broker.close(task_id)
        return

    errors = final_state.get("errors", [])
    report = final_state.get("report", "")
    opinions = final_state.get("opinions", [])
    subtasks = final_state.get("subtasks", [])

    store.update(
        task_id,
        status="done",
        output=report,
        subtasks=subtasks,
        opinions=opinions,
        progress_events=final_state.get("progress_events", []),
        error="; ".join(errors) if errors else None,
    )
    # 最终结果作为一条 SSE 事件推送（必须先于 close，保证缓冲顺序正确）。
    # error 字段携带非致命告警（如某数据源无结果），供前端展示黄色提示。
    broker.publish(
        task_id,
        {
            "type": "result",
            "report": report,
            "opinions": opinions,
            "subtasks": subtasks,
            "error": "; ".join(errors) if errors else None,
        },
    )
    broker.close(task_id)

    # 报告入 Milvus（供 RAG 检索历史调研），失败不影响任务结果
    try:
        from app.repositories.research_repository import get_research_repository

        repo = get_research_repository()
        if repo.available and report:
            repo.save(req.topic, report, task_id)
    except Exception:  # noqa: BLE001
        logger.warning("调研结果写入 Milvus 失败（忽略）", exc_info=True)
