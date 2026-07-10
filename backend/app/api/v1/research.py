"""
数据源与调研任务路由（对应 SpringBoot 的 @RestController）。

从原 backend/main.py 迁移而来，拆成路由 + 服务 + 仓储三层。
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_task_store_dep
from app.schemas.research import ResearchRequest, TaskResponse, TaskResult
from app.services.research_service import run_research_async
from app.services.task_store import TaskStore

router = APIRouter()


@router.get("/sources")
async def list_sources():
    """返回支持的数据源列表。"""
    return {
        "sources": [
            {"id": "reddit", "name": "Reddit", "free": True, "needs_key": False},
            {"id": "hackernews", "name": "Hacker News", "free": True, "needs_key": False},
            {"id": "github", "name": "GitHub", "free": True, "needs_key": False},
            {"id": "arxiv", "name": "arXiv", "free": True, "needs_key": False},
            {"id": "digg", "name": "Digg", "free": True, "needs_key": False},
            {"id": "techmeme", "name": "Techmeme", "free": True, "needs_key": False},
            {
                "id": "youtube",
                "name": "YouTube",
                "free": True,
                "needs_key": False,
                "note": "需安装 yt-dlp",
            },
            {"id": "x", "name": "X/Twitter", "free": False, "needs_key": True},
            {"id": "tiktok", "name": "TikTok", "free": False, "needs_key": True},
            {"id": "instagram", "name": "Instagram", "free": False, "needs_key": True},
            {"id": "bluesky", "name": "Bluesky", "free": True, "needs_key": True},
            {"id": "polymarket", "name": "Polymarket", "free": True, "needs_key": False},
            {"id": "linkedin", "name": "LinkedIn", "free": False, "needs_key": True},
            {"id": "perplexity", "name": "Perplexity", "free": False, "needs_key": True},
        ]
    }


@router.post("/research", response_model=TaskResponse)
async def create_research(
    req: ResearchRequest, store: TaskStore = Depends(get_task_store_dep)
):
    """创建调研任务（异步）。"""
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="调研主题不能为空")

    task_id = store.create(req.topic, req.model_dump())
    asyncio.create_task(run_research_async(task_id, req, store))

    return TaskResponse(
        task_id=task_id,
        status="pending",
        message=f"调研任务已创建：{req.topic}，请轮询 /api/v1/research/{task_id} 获取结果",
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
    return {"message": "任务已删除", "task_id": task_id}
