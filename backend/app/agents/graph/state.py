"""
共享状态（State）定义 —— 多 Agent 协作的"数据总线"。

LangGraph 的核心机制：所有节点读写同一个 ResearchState，
中间结果（子任务、素材、观点）通过 State 在 Agent 之间传递，
而不是靠函数参数层层透传。

并发写规则：
- 检索/清洗节点通过 Send 并行执行，同一轮里多个实例会同时返回
  raw_materials / cleaned_materials / progress_events 的增量，
  这些字段必须声明 operator.add reducer（列表拼接合并），
  否则 LangGraph 抛 InvalidUpdateError（并发写冲突）。
- planner/analyst/writer 串行，普通字段直接覆盖即可。
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class SubTask(TypedDict):
    """Planner 拆解出的子任务。"""

    id: str            # 如 "t1"
    query: str         # 子任务检索查询
    angle: str         # 调研角度说明（如"技术原理"、"社区口碑"）


class Material(TypedDict, total=False):
    """一条检索素材（清洗前后共用同一结构）。"""

    subtask_id: str
    title: str
    url: str
    source: str        # 来源：web/reddit/youtube/juejin...
    snippet: str       # 原始摘要
    content: str       # 清洗后的正文要点（cleaner 填写）
    relevance: float   # 相关度 0-1（cleaner 评分）


class Opinion(TypedDict, total=False):
    """分析 Agent 提取的观点（供报告引用与前端观点图谱）。"""

    id: str
    statement: str           # 观点陈述
    stance: str              # positive/negative/neutral
    evidence_urls: list[str] # 支撑素材链接
    weight: float            # 重要度 0-1


class ProgressEvent(TypedDict):
    """节点执行进度事件（Phase 4 通过 SSE 推给前端）。"""

    node: str          # planner/retriever/cleaner/analyst/writer
    status: str        # start/done/error
    detail: str
    ts: str            # ISO 时间戳


class ResearchState(TypedDict):
    """全图共享状态。"""

    # ===== 输入 =====
    topic: str
    days: int
    sources: list[str]  # 用户勾选的数据源（空 = 全部默认源）

    # ===== Planner 产出（串行，覆盖写）=====
    subtasks: list[SubTask]

    # ===== 检索/清洗产出（并行，add 合并）=====
    raw_materials: Annotated[list[Material], operator.add]
    cleaned_materials: Annotated[list[Material], operator.add]

    # ===== 分析/写作产出（串行，覆盖写）=====
    opinions: list[Opinion]
    report: str

    # ===== 进度事件（所有节点都会追加，add 合并）=====
    progress_events: Annotated[list[ProgressEvent], operator.add]

    # ===== 运行控制 =====
    mock: bool                 # mock 模式：不调外部 API，走演示数据
    errors: Annotated[list[str], operator.add]


def make_event(node: str, status: str, detail: str = "") -> ProgressEvent:
    """构造进度事件（统一时间戳格式）。"""
    from datetime import datetime

    return {
        "node": node,
        "status": status,
        "detail": detail,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }


def initial_state(
    topic: str,
    days: int = 30,
    mock: bool = False,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """构造初始 State（graph.invoke 的入参）。"""
    return {
        "topic": topic,
        "days": days,
        "sources": list(sources or []),
        "subtasks": [],
        "raw_materials": [],
        "cleaned_materials": [],
        "opinions": [],
        "report": "",
        "progress_events": [],
        "mock": mock,
        "errors": [],
    }
