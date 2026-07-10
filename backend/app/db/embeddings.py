"""
Embedding 模型封装。

默认用 OpenAI text-embedding-3-small（1536 维，便宜，支持中英文）。
若需换本地模型，改这里即可，上层代码不变。
"""
from __future__ import annotations

from app.core.config import get_settings


def get_embeddings():
    """返回 LangChain Embeddings 实例。无 API Key 时返回 None。"""
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    from langchain_openai import OpenAIEmbeddings

    kwargs = {"model": settings.embedding_model, "api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url

    return OpenAIEmbeddings(**kwargs)
