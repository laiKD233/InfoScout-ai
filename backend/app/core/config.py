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

    # CLI 引擎（last30days）单次调研超时（秒）。
    # last30days 真实模式是多平台深度爬取，1-3 分钟正常；Reddit 等慢源/被限流时更久。
    # 对齐"10 分钟内出报告"目标，默认 600s（可用 .env 覆盖）。
    research_timeout_seconds: int = 600

    # Web 搜索后端 Key（引擎按 brave -> exa -> serper -> parallel -> keyless 顺序尝试）
    brave_api_key: str = ""
    exa_api_key: str = ""
    serper_api_key: str = ""

    # ===== LLM（LangChain 调用）=====
    openai_api_key: str = ""
    openai_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"

    # ===== 多模型分工（Phase 1 多 Agent 编排）=====
    # fast 档：检索/清洗 Agent 用（成本敏感）。配置了 DeepSeek Key 则走 DeepSeek，
    # 否则回落到上面的 OpenAI 配置——代码不用改，填 Key 即切换。
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    # fast 档回落 OpenAI 时使用的模型（默认与 llm_model 相同即可）
    fast_llm_model: str = "gpt-4o-mini"
    # smart 档：分析/写作 Agent 用（质量敏感），直接用 llm_model

    # ===== Embeddings（用于 Milvus 向量化）=====
    embedding_model: str = "text-embedding-3-small"

    # ===== BGE-Reranker（Milvus 召回后重排，提升检索精度）=====
    # 本地 Cross-Encoder 重排模型；未安装 FlagEmbedding 或模型不可用时自动降级为
    # 仅用向量相似度，不影响主链路。设为空字符串则禁用重排。
    bge_reranker_model: str = "BAAI/bge-reranker-v2-m3"
    bge_reranker_top_k: int = 3

    # ===== MCP（多源数据源 Tools 暴露给外部 Agent）=====
    # 后端内部走 Function Calling（LangChain @tool），同一批数据源函数
    # 同时通过 MCP server 暴露（python -m app.mcp_server），供 Claude 等外部 Agent 调用。
    mcp_server_enabled: bool = True

    # ===== Milvus 向量库 =====
    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "research_results"
    # 若设为 False，则跳过 Milvus 连接，RAG 相关功能降级
    milvus_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    """单例配置，避免重复读取 .env。"""
    return Settings()
