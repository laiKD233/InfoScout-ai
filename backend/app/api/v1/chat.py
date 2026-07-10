"""
Agent 问答路由：新接口，对应 LangChain Agent 能力。

与 /research 的区别：
- /research：直接调 CLI，返回原始报告
- /chat：交给 Agent 决策，可能先检索历史、再调研、再总结
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from app.agents.research_agent import run_agent
from app.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Agent 问答接口。Agent 自主决定是否调用调研/检索工具。"""
    if not req.question.strip():
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="问题不能为空")

    result = run_agent(req.question)
    return ChatResponse(
        answer=result["answer"],
        tools_used=result["tools_used"],
        error=result["error"],
    )
