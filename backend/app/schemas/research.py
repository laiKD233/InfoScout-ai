"""调研相关的请求/响应模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """调研请求（对应前端 POST /api/research 的 body）。"""

    topic: str = Field(..., description="调研主题", examples=["Claude Code vs Cursor"])
    emit: str = Field("md", description="输出格式：compact/json/md/html/brief")
    quick: bool = Field(False, description="低延迟模式")
    deep: bool = Field(False, description="高召回模式")
    days: int = Field(30, description="回溯天数", ge=1, le=90)
    sources: str | None = Field(None, description="逗号分隔的数据源列表，如 reddit,x,youtube")
    mock: bool = Field(False, description="使用 mock 数据（无需 API Key，用于演示）")


class TaskResponse(BaseModel):
    """异步任务创建响应。"""

    task_id: str
    status: str
    message: str


class TaskResult(BaseModel):
    """任务结果。"""

    task_id: str
    status: str
    topic: str
    output: str | None = None
    error: str | None = None
    # 诊断字段（仅用于排查，正常使用可忽略）
    returncode: int | None = None
    stderr_tail: str | None = None
    cmd: list[str] | None = None
