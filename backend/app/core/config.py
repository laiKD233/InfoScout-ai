"""
集中配置：从 backend/.env 读取，对应 SpringBoot 的 application.yml + @Value。
使用 pydantic-settings 做类型校验与默认值。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# 路径常量（供其他模块直接引用）
# app/core/config.py -> app/core -> app -> backend -> 项目根
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
SCRIPTS_DIR = PROJECT_ROOT / "skills" / "last30days" / "scripts"
CLI_ENTRY = SCRIPTS_DIR / "last30days.py"
RESULTS_DIR = PROJECT_ROOT / "results"


class Settings(BaseSettings):
    """全局配置。字段名与 .env 中变量名（大小写不敏感）一一对应。"""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ===== 调研引擎 =====
    last30days_memory_dir: str = str(RESULTS_DIR)

    # ===== LLM（LangChain 调用）=====
    openai_api_key: str = ""
    openai_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"

    # ===== Embeddings（用于 Milvus 向量化）=====
    embedding_model: str = "text-embedding-3-small"

    # ===== Milvus 向量库 =====
    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "research_results"
    # 若设为 False，则跳过 Milvus 连接，RAG 相关功能降级
    milvus_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    """单例配置，避免重复读取 .env。"""
    return Settings()
