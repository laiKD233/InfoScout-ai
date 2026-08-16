"""
双模型工厂：多 Agent 按角色取不同档位的 LLM，控制成本。

分工策略（对应"多模型分工控成本"）：
- fast  档 → 检索/清洗 Agent：调用量大、任务简单（关键词生成、去噪、结构化），
             优先 DeepSeek（便宜一个数量级），未配 DeepSeek 时回落 OpenAI。
- smart 档 → 分析/写作 Agent：需要强推理与长文生成，优先 OpenAI（llm_model），
             只配了 DeepSeek 时回落到 DeepSeek（全链路单 Key 体验）。

上层节点只写 get_llm("fast") / get_llm("smart")，不关心背后是哪家——
将来加新供应商只改这一个文件。
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from app.core.config import get_settings

logger = logging.getLogger(__name__)

Tier = Literal["fast", "smart"]


@lru_cache(maxsize=4)
def get_llm(tier: Tier = "smart", temperature: float = 0.3):
    """按档位返回 ChatOpenAI 实例；完全无 Key 时返回 None（调用方走降级）。

    选择优先级：
    - fast 档：DeepSeek（控成本）> OpenAI 回落。
    - smart 档：OpenAI（质量）> DeepSeek 回落（便于只配一个 DeepSeek Key 时
      分析/写作也能跑，实现"全链路 DeepSeek"）。
    """
    settings = get_settings()
    from langchain_openai import ChatOpenAI

    def _deepseek() -> ChatOpenAI:
        # DeepSeek 走 OpenAI 兼容协议，换 base_url 即可
        return ChatOpenAI(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            temperature=temperature,
        )

    # fast 档优先 DeepSeek
    if tier == "fast" and settings.deepseek_api_key:
        logger.info("fast 档 LLM: DeepSeek %s", settings.deepseek_model)
        return _deepseek()

    # OpenAI（或任意兼容端点）作为主路径
    if settings.openai_api_key:
        model = settings.fast_llm_model if tier == "fast" else settings.llm_model
        kwargs: dict = {
            "model": model,
            "api_key": settings.openai_api_key,
            "temperature": temperature,
        }
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return ChatOpenAI(**kwargs)

    # smart 档回落 DeepSeek：没配 OpenAI 时，分析/写作也用 DeepSeek
    if tier == "smart" and settings.deepseek_api_key:
        logger.info("smart 档 LLM 回落 DeepSeek %s", settings.deepseek_model)
        return _deepseek()

    return None


def llm_available() -> bool:
    """是否有任何可用 LLM（graph 服务据此决定真跑还是 mock）。"""
    s = get_settings()
    return bool(s.openai_api_key or s.deepseek_api_key)
