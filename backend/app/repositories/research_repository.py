"""
调研结果仓储层：把调研报告向量化存入 Milvus，并支持相似检索。

对应 SpringBoot 的 @Repository。数据源是 Milvus 向量库而非关系库。
"""
from __future__ import annotations

import logging
from datetime import datetime

from app.core.config import get_settings
from app.db.embeddings import get_embeddings
from app.db.milvus_client import get_milvus_client

logger = logging.getLogger(__name__)

# text-embedding-3-small 的向量维度
_EMBEDDING_DIM = 1536


class ResearchRepository:
    """调研结果的向量存储与检索。Milvus 不可用时 available=False，方法静默降级。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = get_milvus_client()
        self.embeddings = get_embeddings() if self.client else None
        self.collection_name = self.settings.milvus_collection
        if self.client:
            self._ensure_collection()

    @property
    def available(self) -> bool:
        return self.client is not None and self.embeddings is not None

    def _ensure_collection(self) -> None:
        """若 collection 不存在则创建。"""
        from pymilvus import DataType

        if self.client.has_collection(self.collection_name):
            return

        schema = self.client.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=_EMBEDDING_DIM)
        schema.add_field("topic", DataType.VARCHAR, max_length=500)
        schema.add_field("content", DataType.VARCHAR, max_length=65535)
        schema.add_field("task_id", DataType.VARCHAR, max_length=64)
        schema.add_field("created_at", DataType.VARCHAR, max_length=32)

        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector", index_type="AUTOINDEX", metric_type="COSINE"
        )
        self.client.create_collection(
            self.collection_name, schema=schema, index_params=index_params
        )
        logger.info("Milvus collection 已创建: %s", self.collection_name)

    def save(self, topic: str, content: str, task_id: str) -> bool:
        """把一条调研结果向量化并存入 Milvus。"""
        if not self.available:
            logger.debug("Milvus 不可用，跳过保存: task_id=%s", task_id)
            return False

        # embedding 对 token 数有上限，截断保护
        text = content[:8000]
        vector = self.embeddings.embed_query(text)
        self.client.insert(
            self.collection_name,
            {
                "vector": vector,
                "topic": topic[:500],
                "content": content[:65535],
                "task_id": task_id,
                "created_at": datetime.now().isoformat(),
            },
        )
        logger.info("调研结果已存入 Milvus: topic=%s, task_id=%s", topic, task_id)
        return True

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """基于 query 的语义相似检索历史调研结果（向量召回 + BGE 重排）。"""
        if not self.available:
            return []

        vector = self.embeddings.embed_query(query)
        # 先多召回一些候选，交给 BGE-Reranker 精排后再截断，提升命中质量
        recall_k = max(top_k * 3, top_k)
        results = self.client.search(
            self.collection_name,
            [vector],
            limit=recall_k,
            output_fields=["topic", "content", "task_id", "created_at"],
        )

        out: list[dict] = []
        for hits in results:
            for hit in hits:
                entity = hit.get("entity", {})
                out.append(
                    {
                        "topic": entity.get("topic"),
                        "content": entity.get("content"),
                        "task_id": entity.get("task_id"),
                        "created_at": entity.get("created_at"),
                        "score": hit.get("distance"),
                    }
                )

        # BGE-Reranker 精排：不可用时 rerank_documents 原样返回（保持向量顺序）
        from app.db.reranker import rerank_documents

        out = rerank_documents(query, out)
        return out[:top_k]


_repo: ResearchRepository | None = None


def get_research_repository() -> ResearchRepository:
    """单例仓储。首次调用时尝试连接 Milvus。"""
    global _repo
    if _repo is None:
        _repo = ResearchRepository()
    return _repo
