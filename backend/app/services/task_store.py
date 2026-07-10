"""
任务存储（内存实现，演示用）。

对应 SpringBoot 里用一个 ConcurrentHashMap 存任务状态。
生产环境应替换为 Redis 或数据库——见类内注释。
"""
from __future__ import annotations

import uuid
from typing import Any


class TaskStore:
    """内存任务队列。进程重启后数据丢失，生产环境请换 Redis / Celery。"""

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}

    def create(self, topic: str, request: dict[str, Any]) -> str:
        task_id = uuid.uuid4().hex[:12]
        self._tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "topic": topic,
            "output": None,
            "error": None,
            "request": request,
        }
        return task_id

    def get(self, task_id: str) -> dict[str, Any] | None:
        return self._tasks.get(task_id)

    def update(self, task_id: str, **fields: Any) -> None:
        if task_id in self._tasks:
            self._tasks[task_id].update(fields)

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._tasks.values())

    def delete(self, task_id: str) -> bool:
        return self._tasks.pop(task_id, None) is not None


# 单例（FastAPI 依赖注入时复用）
_task_store = TaskStore()


def get_task_store() -> TaskStore:
    return _task_store
