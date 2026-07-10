"""Agent 问答相关的请求/响应模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Agent 问答请求。"""

    question: str = Field(..., description="用户问题", examples=["Claude Code 最近有什么新动态？"])
    mock: bool = Field(True, description="调研工具是否使用 mock 数据（演示用）")


class ChatResponse(BaseModel):
    """Agent 问答响应。"""

    answer: str
    tools_used: list[str] = Field(default_factory=list, description="Agent 调用的工具列表")
    error: str | None = None
