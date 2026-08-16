"""
StateGraph 编排 —— 把 5 个 Agent 节点组装成研究图。

拓扑（对应"检索清洗并行提速、分析写作串行衔接"）：

    planner ──Send×N──> retriever(并行) ──> join_retrieval
            ──Send×N──> cleaner(并行)  ──> join_cleaning ──> analyst ──> writer ──> END

并行机制：
- LangGraph 的 Send API：conditional edge 返回 Send 列表，同一超步内
  N 个 retriever/cleaner 实例并发执行，产出经 State 的 add reducer 合并。
- fan-in 用无操作 join 节点：并行实例全部完成后 join 只执行一次，
  再从 join 做下一次分发/串行衔接（若直接在并行节点上挂 conditional
  edge，每个实例都会触发一次路由，导致重复分发）。
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents.graph.nodes.analyst import analyst_node
from app.agents.graph.nodes.cleaner import cleaner_node
from app.agents.graph.nodes.planner import planner_node
from app.agents.graph.nodes.retriever import retriever_node
from app.agents.graph.nodes.writer import writer_node
from app.agents.graph.state import ResearchState


def _dispatch_retrieval(state: ResearchState) -> list[Send]:
    """planner 完成后：按子任务 fan-out 到 retriever 并行实例。"""
    return [
        Send(
            "retriever",
            {
                "subtask": t,
                "mock": state.get("mock", False),
                "days": state.get("days", 30),
                "sources": state.get("sources", []),
            },
        )
        for t in state["subtasks"]
    ]


def _dispatch_cleaning(state: ResearchState) -> list[Send]:
    """检索全部完成后：素材按子任务分组，fan-out 到 cleaner 并行实例。"""
    grouped: dict[str, list] = defaultdict(list)
    for m in state.get("raw_materials", []):
        grouped[m.get("subtask_id", "")].append(m)

    sends = [
        Send(
            "cleaner",
            {
                "subtask": t,
                "materials": grouped.get(t["id"], []),
                "topic": state["topic"],
                "mock": state.get("mock", False),
            },
        )
        for t in state["subtasks"]
        if grouped.get(t["id"])
    ]
    # 所有子任务都没检索到素材时仍需推进到 analyst（其内部会降级处理）
    return sends or [
        Send(
            "cleaner",
            {"subtask": {"id": "t0", "query": state["topic"], "angle": "兜底"},
             "materials": [], "topic": state["topic"], "mock": state.get("mock", False)},
        )
    ]


def _join(_state: ResearchState) -> dict:
    """无操作 fan-in 节点：等待同一超步的并行实例全部完成。"""
    return {}


def build_research_graph():
    """构建并编译研究图。"""
    g = StateGraph(ResearchState)

    g.add_node("planner", planner_node)
    g.add_node("retriever", retriever_node)
    g.add_node("join_retrieval", _join)
    g.add_node("cleaner", cleaner_node)
    g.add_node("join_cleaning", _join)
    g.add_node("analyst", analyst_node)
    g.add_node("writer", writer_node)

    g.add_edge(START, "planner")
    # fan-out 1：planner -> N 个 retriever
    g.add_conditional_edges("planner", _dispatch_retrieval, ["retriever"])
    g.add_edge("retriever", "join_retrieval")
    # fan-out 2：join_retrieval -> N 个 cleaner
    g.add_conditional_edges("join_retrieval", _dispatch_cleaning, ["cleaner"])
    g.add_edge("cleaner", "join_cleaning")
    # 串行衔接：分析 -> 写作
    g.add_edge("join_cleaning", "analyst")
    g.add_edge("analyst", "writer")
    g.add_edge("writer", END)

    return g.compile()


@lru_cache(maxsize=1)
def get_research_graph():
    """编译后的图单例（编译开销只付一次）。"""
    return build_research_graph()
