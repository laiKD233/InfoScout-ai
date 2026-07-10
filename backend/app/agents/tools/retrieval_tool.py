"""
检索工具：从 Milvus 中检索历史调研结果（RAG）。

当用户问题可能已被之前的调研覆盖时，Agent 调用此工具复用历史结果，
无需重新发起全网调研。
"""
from __future__ import annotations

from langchain_core.tools import tool

from app.repositories.research_repository import get_research_repository


@tool
def search_history_research(query: str) -> str:
    """检索历史调研结果。当问题可能已被之前的调研覆盖时使用，避免重复调研。

    Args:
        query: 检索查询，应与用户问题语义相关。
    """
    repo = get_research_repository()
    if not repo.available:
        return "历史调研检索不可用（Milvus 未连接），请改用 research_topic 发起新调研。"

    results = repo.search(query, top_k=3)
    if not results:
        return "未找到相关历史调研，请改用 research_topic 发起新调研。"

    blocks = []
    for i, r in enumerate(results, 1):
        blocks.append(
            f"### 历史调研 {i}: {r['topic']}\n"
            f"相关度: {r['score']:.3f}\n"
            f"内容摘要:\n{r['content'][:1500]}"
        )
    return "\n\n---\n\n".join(blocks)
