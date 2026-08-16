"""
BGE-Reranker 封装 —— Milvus 向量召回后的精排（Cross-Encoder）。

设计原则：
- 可选增强：未安装 FlagEmbedding、未配置模型或加载失败时返回 None，
  上层退化为仅用向量相似度，不影响调研主链路。
- 惰性加载 + 单例：模型只加载一次，首次调用触发下载/加载。
- 输入输出与 Milvus 检索解耦：rerank(query, docs) 收文档文本，返回
  按相关性降序的 (index, score) 列表。

BGE-Reranker（BAAI/bge-reranker-v2-m3 等）是面向中文/多语的 Cross-Encoder，
对 query-document 对做精细打分，显著优于单纯的 embedding 余弦相似度。
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_reranker: Any = None
_reranker_model: str | None = None


def get_reranker():
    """返回 BGE Reranker 单例；不可用时返回 None。

    返回值为可调用对象 reranker(query, texts) -> list[float]，或 None。
    """
    global _reranker, _reranker_model

    settings = get_settings()
    model = (settings.bge_reranker_model or "").strip()
    if not model:
        return None

    if _reranker is not None and _reranker_model == model:
        return _reranker

    try:
        # FlagEmbedding 依赖 torch，体积较大，作为可选依赖按需导入。
        from FlagEmbedding import FlagReranker  # type: ignore

        logger.info("加载 BGE-Reranker: %s", model)
        _reranker = FlagReranker(model, use_fp16=True)
        _reranker_model = model
        return _reranker
    except Exception as e:  # noqa: BLE001
        logger.warning("BGE-Reranker 不可用（降级为向量相似度）: %s", e)
        _reranker = None
        _reranker_model = model
        return None


def rerank_documents(query: str, docs: list[dict]) -> list[dict]:
    """对检索候选用 BGE-Reranker 精排。

    docs: [{"content": str, ...}]，返回按重排分降序排列的原列表。
    重排不可用时原样返回（保持向量相似度顺序）。
    """
    reranker = get_reranker()
    if reranker is None or not docs:
        return docs

    texts = [d.get("content", "") for d in docs]
    try:
        # FlagReranker.compute_score 单对打分；这里批量做 query-文档对。
        pairs = [[query, t] for t in texts]
        scores = reranker.compute_score(pairs, normalize=True)
        if isinstance(scores, (int, float)):
            scores = [float(scores)]
        scored = [
            {**d, "rerank_score": float(s)}
            for d, s in zip(docs, scores)
        ]
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored
    except Exception as e:  # noqa: BLE001
        logger.warning("BGE-Reranker 打分失败，保持向量顺序: %s", e)
        return docs
