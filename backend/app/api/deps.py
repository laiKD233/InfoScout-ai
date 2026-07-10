"""依赖注入（对应 SpringBoot 的 @Autowired / @Bean）。"""
from __future__ import annotations

from app.services.task_store import TaskStore, get_task_store


def get_task_store_dep() -> TaskStore:
    """FastAPI 路由通过 Depends(get_task_store_dep) 注入单例。"""
    return get_task_store()
