"""
数据源与调研任务路由（对应 SpringBoot 的 @RestController）。

从原 backend/main.py 迁移而来，拆成路由 + 服务 + 仓储三层。
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_task_store_dep
from app.schemas.research import ResearchRequest, TaskResponse, TaskResult
from app.services.graph_research_service import run_graph_research_async
from app.services.progress_broker import get_progress_broker
from app.services.research_service import run_research_async
from app.services.task_store import TaskStore

router = APIRouter()

# 数据源清单。engines 字段标明该数据源由哪个引擎支持：
# - "graph"：多 Agent 图引擎（web/reddit/youtube/juejin/hackernews/github，Function Calling + MCP）
#   其中图引擎默认源为境内可达的国内源（web=必应中国、juejin、bilibili、segmentfault）；
#   reddit/youtube/hackernews/github 为外网源，仅在有外网的 CLI 引擎里可用。
# - "cli"  ：last30days CLI 引擎（对比基线）
_SOURCES = [
    # ===== 多 Agent 图引擎支持（境内可达源）=====
    {"id": "web", "name": "Web 通用（必应中国）", "free": True, "needs_key": False, "engines": ["graph"]},
    {"id": "juejin", "name": "稀土掘金", "free": True, "needs_key": False, "engines": ["graph"]},
    {"id": "bilibili", "name": "B站", "free": True, "needs_key": False, "engines": ["graph"], "note": "中文主流视频平台（境内可达）"},
    {"id": "segmentfault", "name": "思否社区", "free": True, "needs_key": False, "engines": ["graph"], "note": "中文技术问答社区（境内可达）"},
    # ===== 外网源（仅 CLI / 有外网环境）=====
    {"id": "reddit", "name": "Reddit", "free": True, "needs_key": False, "engines": ["cli"]},
    {
        "id": "youtube",
        "name": "YouTube",
        "free": True,
        "needs_key": False,
        "engines": ["cli"],
        "note": "CLI 深度转录需 yt-dlp",
    },
    {
        "id": "hackernews",
        "name": "Hacker News",
        "free": True,
        "needs_key": False,
        "engines": ["cli"],
        "note": "官方 Algolia API",
    },
    {
        "id": "github",
        "name": "GitHub",
        "free": True,
        "needs_key": False,
        "engines": ["cli"],
        "note": "官方搜索 API",
    },
    # ===== 仅 last30days CLI 引擎支持 =====
    {"id": "arxiv", "name": "arXiv", "free": True, "needs_key": False, "engines": ["cli"]},
    {"id": "digg", "name": "Digg", "free": True, "needs_key": False, "engines": ["cli"]},
    {"id": "techmeme", "name": "Techmeme", "free": True, "needs_key": False, "engines": ["cli"]},
    {"id": "x", "name": "X/Twitter", "free": False, "needs_key": True, "engines": ["cli"]},
    {"id": "tiktok", "name": "TikTok", "free": False, "needs_key": True, "engines": ["cli"]},
    {"id": "instagram", "name": "Instagram", "free": False, "needs_key": True, "engines": ["cli"]},
    {"id": "bluesky", "name": "Bluesky", "free": True, "needs_key": True, "engines": ["cli"]},
    {"id": "polymarket", "name": "Polymarket", "free": True, "needs_key": False, "engines": ["cli"]},
    {"id": "linkedin", "name": "LinkedIn", "free": False, "needs_key": True, "engines": ["cli"]},
    {"id": "perplexity", "name": "Perplexity", "free": False, "needs_key": True, "engines": ["cli"]},
]

# 图引擎专属数据源（CLI 引擎无法检索；图引擎默认境内源）
_GRAPH_ONLY_SOURCES = {"juejin", "web", "bilibili", "segmentfault"}


@router.get("/sources")
async def list_sources():
    """返回支持的数据源列表（含每个源的引擎支持情况）。"""
    return {"sources": _SOURCES}


@router.post("/research", response_model=TaskResponse)
async def create_research(
    req: ResearchRequest, store: TaskStore = Depends(get_task_store_dep)
):
    """创建调研任务（异步，last30days CLI 引擎）。"""
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="调研主题不能为空")

    # CLI 引擎（last30days）不支持 web/juejin 等图引擎专属源，提前拒绝并给出指引
    selected = {s.strip() for s in (req.sources or "").split(",") if s.strip()}
    graph_only = selected & _GRAPH_ONLY_SOURCES
    if graph_only:
        raise HTTPException(
            status_code=400,
            detail=(
                f"数据源 {', '.join(sorted(graph_only))} 仅多 Agent 图引擎支持，"
                "请改用 POST /api/v1/research/graph"
            ),
        )

    task_id = store.create(req.topic, req.model_dump())
    asyncio.create_task(run_research_async(task_id, req, store))

    return TaskResponse(
        task_id=task_id,
        status="pending",
        message=f"调研任务已创建：{req.topic}，请轮询 /api/v1/research/{task_id} 获取结果",
    )


@router.post("/research/graph", response_model=TaskResponse)
async def create_graph_research(
    req: ResearchRequest, store: TaskStore = Depends(get_task_store_dep)
):
    """创建多 Agent 图编排调研任务（LangGraph：检索/清洗并行 + 分析/写作串行）。"""
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="调研主题不能为空")

    task_id = store.create(req.topic, req.model_dump())
    asyncio.create_task(run_graph_research_async(task_id, req, store))

    return TaskResponse(
        task_id=task_id,
        status="pending",
        message=f"多 Agent 调研任务已创建：{req.topic}，请轮询 /api/v1/research/{task_id} 获取结果",
    )


@router.get("/research/{task_id}", response_model=TaskResult)
async def get_research(task_id: str, store: TaskStore = Depends(get_task_store_dep)):
    """查询任务状态与结果。"""
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    return TaskResult(
        task_id=task_id,
        status=task["status"],
        topic=task["topic"],
        output=task["output"],
        error=task["error"],
        returncode=task.get("returncode"),
        stderr_tail=task.get("stderr_tail"),
        cmd=task.get("cmd"),
        engine=task.get("engine"),
        subtasks=task.get("subtasks"),
        opinions=task.get("opinions"),
        progress_events=task.get("progress_events"),
    )


@router.get("/research/{task_id}/stream")
async def stream_research(
    task_id: str, store: TaskStore = Depends(get_task_store_dep)
):
    """SSE 实时进度流（多 Agent 图引擎）。事件类型：

    - {"type": "progress", "event": {node/status/detail/ts}}  节点进度
    - {"type": "result", "report": ..., "opinions": ..., "subtasks": ...}  最终结果
    - {"type": "error", "detail": ...}  执行失败
    """
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    broker = get_progress_broker()

    async def event_generator():
        q = broker.subscribe(task_id)
        try:
            while True:
                item = await asyncio.to_thread(q.get)
                if broker.is_sentinel(item):
                    break
                if isinstance(item, dict) and item.get("type") == "end":
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        finally:
            broker.unsubscribe(task_id, q)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/research")
async def list_research(store: TaskStore = Depends(get_task_store_dep)):
    """列出所有任务。"""
    tasks = store.list_all()
    return {
        "total": len(tasks),
        "tasks": [
            {"task_id": t["task_id"], "topic": t["topic"], "status": t["status"]}
            for t in tasks
        ],
    }


@router.delete("/research/{task_id}")
async def delete_research(task_id: str, store: TaskStore = Depends(get_task_store_dep)):
    """删除任务。"""
    if not store.delete(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    get_progress_broker().purge(task_id)
    return {"message": "任务已删除", "task_id": task_id}
