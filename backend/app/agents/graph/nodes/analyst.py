"""
分析 Agent 节点 —— 串行执行（在所有清洗完成后运行）。

从清洗后的素材中提取结构化观点（statement/stance/evidence/weight），
写入 state.opinions：既是写作 Agent 的输入，也是前端 ECharts
观点图谱的数据源。用 smart 档模型（需要强推理）。
"""
from __future__ import annotations

import logging

from app.agents.graph.nodes.common import parse_json_block
from app.agents.graph.state import Opinion, ResearchState, make_event
from app.core.llm import get_llm

logger = logging.getLogger(__name__)

_PROMPT = """你是资深行业分析师。基于以下关于「{topic}」的清洗后素材，提取 5-8 个核心观点。

素材（按调研角度分组）：
{materials}

每个观点要求：
- statement：一句话观点陈述（有信息量，不是泛泛而谈）
- stance：该观点的倾向 positive/negative/neutral
- evidence_urls：支撑该观点的素材 URL（从上面素材中选，1-3 个）
- weight：重要度 0-1（依据素材支撑强度与信息价值）

只输出 JSON 数组，元素形如：
{{"statement": "...", "stance": "neutral", "evidence_urls": ["..."], "weight": 0.8}}"""

_MAX_MATERIALS = 30


def _format_materials(state: ResearchState) -> str:
    """按子任务角度分组格式化素材（截断保护 token）。"""
    angle_by_id = {t["id"]: t["angle"] for t in state.get("subtasks", [])}
    lines: list[str] = []
    for m in state.get("cleaned_materials", [])[:_MAX_MATERIALS]:
        angle = angle_by_id.get(m.get("subtask_id", ""), "其他")
        lines.append(
            f"- [{angle}] {m.get('title', '')}\n"
            f"  要点: {m.get('content', '')[:400]}\n"
            f"  链接: {m.get('url', '')}"
        )
    return "\n".join(lines)


def _mock_opinions(state: ResearchState) -> list[Opinion]:
    """mock/降级：从素材直接生成占位观点，保证链路可走。"""
    ops: list[Opinion] = []
    for i, m in enumerate(state.get("cleaned_materials", [])[:5]):
        ops.append(
            {
                "id": f"o{i + 1}",
                "statement": f"[Mock 观点] {m.get('title', '')}",
                "stance": "neutral",
                "evidence_urls": [m.get("url", "")],
                "weight": 0.5,
            }
        )
    return ops


def analyst_node(state: ResearchState) -> dict:
    """提取观点，写入 state.opinions。"""
    n_materials = len(state.get("cleaned_materials", []))
    events = [make_event("analyst", "start", f"基于 {n_materials} 条素材提取观点")]

    opinions: list[Opinion] = []
    errors: list[str] = []

    llm = None if state.get("mock") else get_llm("smart")
    if llm is not None and n_materials:
        try:
            resp = llm.invoke(
                _PROMPT.format(topic=state["topic"], materials=_format_materials(state))
            )
            parsed = parse_json_block(getattr(resp, "content", ""))
            if isinstance(parsed, list):
                for i, item in enumerate(parsed[:10]):
                    if isinstance(item, dict) and item.get("statement"):
                        opinions.append(
                            {
                                "id": f"o{i + 1}",
                                "statement": str(item["statement"]),
                                "stance": str(item.get("stance", "neutral")),
                                "evidence_urls": [
                                    str(u) for u in item.get("evidence_urls", []) if u
                                ],
                                "weight": float(item.get("weight", 0.5)),
                            }
                        )
        except Exception as e:  # noqa: BLE001
            logger.exception("analyst LLM 调用失败")
            errors.append(f"analyst: {e}")
            events.append(make_event("analyst", "error", str(e)))

    if not opinions:
        opinions = _mock_opinions(state)

    events.append(make_event("analyst", "done", f"提取出 {len(opinions)} 个观点"))
    return {"opinions": opinions, "progress_events": events, "errors": errors}
