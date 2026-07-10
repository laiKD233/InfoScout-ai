"""
InfoScout AI — FastAPI 应用入口（分层版）。

职责：
1. 创建 FastAPI 实例 + 中间件
2. 挂载 v1 路由
3. 启动时初始化 Milvus（失败则降级）

不再包含业务逻辑——业务在 services/、agents/、repositories/ 各层。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.chat import router as chat_router
from app.api.v1.research import router as research_router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时预连 Milvus（失败降级，不阻断启动）。"""
    settings = get_settings()
    if settings.milvus_enabled:
        try:
            # 首次调用触发连接，失败会被仓储层捕获
            from app.repositories.research_repository import get_research_repository

            repo = get_research_repository()
            logger.info("Milvus 仓储就绪: available=%s", repo.available)
        except Exception as e:  # noqa: BLE001
            logger.warning("Milvus 初始化失败（RAG 降级）: %s", e)
    else:
        logger.info("Milvus 未启用")

    yield
    logger.info("InfoScout AI 关闭")


app = FastAPI(
    title="InfoScout AI",
    description="全网智能调研 Agent — 输入主题自动检索多平台，生成带引用的研究简报",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由（所有 v1 接口前缀 /api/v1）
app.include_router(research_router, prefix="/api/v1", tags=["research"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])


@app.get("/")
async def root():
    """健康检查。"""
    return {
        "name": "InfoScout AI",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "research": "/api/v1/research",
            "chat": "/api/v1/chat",
            "sources": "/api/v1/sources",
        },
    }
