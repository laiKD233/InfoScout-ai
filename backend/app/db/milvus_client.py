"""
Milvus 连接管理（单例）。

Milvus 不可用时返回 None，上层据此降级——调研功能不受影响。
"""
from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client = None


def get_milvus_client():
    """返回 MilvusClient 单例；未启用或连接失败时返回 None。"""
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    if not settings.milvus_enabled:
        logger.info("Milvus 已禁用（milvus_enabled=False）")
        return None

    try:
        from pymilvus import MilvusClient

        _client = MilvusClient(uri=settings.milvus_uri)
        logger.info("Milvus 已连接: %s", settings.milvus_uri)
        return _client
    except Exception as e:  # noqa: BLE001
        logger.warning("Milvus 连接失败，RAG 功能将降级: %s", e)
        return None
