"""
Planner 节点 —— Plan-and-Execute 的 "Plan" 阶段。

把调研目标拆解为 3-5 个互补角度的子任务，后续由 Send 按子任务
fan-out 给检索 Agent 并行执行。用 fast 档模型（任务简单，控成本）。
"""
from __future__ import annotations

import logging

from app.agents.graph.nodes.common import parse_json_block
from app.agents.graph.state import ResearchState, SubTask, make_event
from app.core.llm import get_llm

logger = logging.getLogger(__name__)

_PROMPT = """你是调研规划专家。请把下面的调研主题拆解为 {n} 个互补的子任务，\
覆盖不同信息角度（如：最新动态、技术/产品细节、社区口碑与争议、竞品对比、数据与案例）。

调研主题：{topic}
时间范围：最近 {days} 天

只输出 JSON 数组，每个元素形如：
{{"query": "用于搜索引擎的具体查询词", "angle": "该子任务的调研角度"}}

要求：query 要具体可搜索（含主题关键词），不要输出 JSON 以外的任何内容。"""

_DEFAULT_N = 4


def _fallback_subtasks(topic: str) -> list[SubTask]:
    """无 LLM / 解析失败时的规则拆解，保证图能继续走。"""
    angles = [
        ("最新动态", f"{topic} 最新进展"),
        ("技术细节", f"{topic} 原理 实现"),
        ("社区口碑", f"{topic} 评价 争议"),
        ("对比与案例", f"{topic} 对比 案例"),
    ]
    return [
        {"id": f"t{i + 1}", "query": q, "angle": a}
        for i, (a, q) in enumerate(angles)
    ]


def planner_node(state: ResearchState) -> dict:
    """拆解子任务，写入 state.subtasks。"""
    topic = state["topic"]
    events = [make_event("planner", "start", f"拆解调研目标：{topic}")]

    subtasks: list[SubTask] = []
    if not state.get("mock"):
        llm = get_llm("fast")
        if llm is not None:
            try:
                resp = llm.invoke(
                    _PROMPT.format(n=_DEFAULT_N, topic=topic, days=state.get("days", 30))
                )
                parsed = parse_json_block(getattr(resp, "content", ""))
                if isinstance(parsed, list):
                    for i, item in enumerate(parsed[:6]):
                        if isinstance(item, dict) and item.get("query"):
                            subtasks.append(
                                {
                                    "id": f"t{i + 1}",
                                    "query": str(item["query"]),
                                    "angle": str(item.get("angle", "")),
                                }
                            )
            except Exception as e:  # noqa: BLE001
                logger.exception("planner LLM 调用失败，走规则拆解")
                events.append(make_event("planner", "error", str(e)))

    if not subtasks:
        subtasks = _fallback_subtasks(topic)

    events.append(
        make_event(
            "planner", "done", f"拆解出 {len(subtasks)} 个子任务：" + "；".join(t["angle"] for t in subtasks)
        )
    )
    return {"subtasks": subtasks, "progress_events": events}
