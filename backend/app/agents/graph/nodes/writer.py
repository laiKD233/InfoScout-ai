"""
写作 Agent 节点 —— 串行执行（analyst 之后，与其共享 State 保证上下文一致）。

基于观点 + 清洗素材生成结构化 Markdown 调研报告（带引用链接），
写入 state.report。用 smart 档模型（长文生成质量敏感）。
"""
from __future__ import annotations

import logging

from app.agents.graph.state import ResearchState, make_event
from app.core.llm import get_llm

logger = logging.getLogger(__name__)

_PROMPT = """你是专业调研报告撰写人。基于以下观点与素材，撰写「{topic}」的调研报告。

## 核心观点（分析 Agent 已提取）
{opinions}

## 支撑素材
{materials}

报告要求（Markdown 格式）：
1. `# {topic} 调研报告` 开头，含"调研范围：最近 {days} 天"
2. 章节：**执行摘要**（3-5 句）、**关键发现**（按观点展开，每条附来源链接）、
   **不同立场与争议**（对比 positive/negative 观点）、**结论与建议**
3. 所有论断必须来自给定观点/素材并附引用链接，不得编造
4. 若给定观点与素材均为空，直接输出"未检索到素材，无法生成报告"，禁止编造任何事实、数据、模型名、公司名或链接
5. 用中文撰写，报告直接输出，不要额外解释"""

_MAX_MATERIALS = 25


def _format_opinions(state: ResearchState) -> str:
    lines = []
    for o in state.get("opinions", []):
        urls = "、".join(o.get("evidence_urls", [])[:3])
        lines.append(
            f"- [{o.get('stance', 'neutral')}] (权重 {o.get('weight', 0.5)}) "
            f"{o.get('statement', '')} 来源: {urls}"
        )
    return "\n".join(lines)


def _format_materials(state: ResearchState) -> str:
    lines = []
    for m in state.get("cleaned_materials", [])[:_MAX_MATERIALS]:
        lines.append(f"- {m.get('title', '')}: {m.get('content', '')[:300]} ({m.get('url', '')})")
    return "\n".join(lines)


def _mock_report(state: ResearchState) -> str:
    """mock/降级：用模板拼接报告，保证链路产出完整。"""
    parts = [
        f"# {state['topic']} 调研报告",
        f"\n> 调研范围：最近 {state.get('days', 30)} 天 | 模式：{'Mock 演示' if state.get('mock') else '降级模板'}\n",
        "## 执行摘要\n",
        f"本次调研围绕「{state['topic']}」拆解为 {len(state.get('subtasks', []))} 个子任务，"
        f"共收集素材 {len(state.get('raw_materials', []))} 条，"
        f"清洗后保留 {len(state.get('cleaned_materials', []))} 条，"
        f"提取观点 {len(state.get('opinions', []))} 个。\n",
        "## 关键发现\n",
    ]
    for o in state.get("opinions", []):
        urls = " ".join(f"[来源]({u})" for u in o.get("evidence_urls", [])[:2])
        parts.append(f"- {o.get('statement', '')} {urls}")
    parts.append("\n## 结论与建议\n\n（配置 LLM API Key 后可生成完整分析结论。）")
    return "\n".join(parts)


def _empty_report(state: ResearchState) -> str:
    """无素材时的诚实报告：说明未检索到并带上错误原因，绝不编造。"""
    reasons = "; ".join(state.get("errors", [])) or "未知"
    return (
        f"# {state['topic']} 调研报告\n\n"
        f"> 调研范围：最近 {state.get('days', 30)} 天\n\n"
        "## 结论\n\n"
        "本次调研**未检索到任何素材**，无法生成可靠报告。\n\n"
        f"- 检索错误：{reasons}\n"
        "- 可能原因：后端无法访问外网、所选数据源被限流/被墙，或主题过于冷门/不存在。\n"
        "- 建议：确认后端网络后，换一个真实存在、有公开讨论的主题，或勾选可用的数据源重试。\n"
    )


def writer_node(state: ResearchState) -> dict:
    """生成最终报告，写入 state.report。"""
    n_materials = len(state.get("cleaned_materials", []))
    n_opinions = len(state.get("opinions", []))
    events = [
        make_event(
            "writer", "start",
            f"基于 {n_opinions} 个观点 / {n_materials} 条素材撰写报告",
        )
    ]

    report = ""
    errors: list[str] = []

    # 无任何证据时不调用 LLM：避免模型在空输入上幻觉式编造报告
    if n_materials == 0 and n_opinions == 0:
        report = _empty_report(state)
        errors.append("writer: 无素材可写，已跳过 LLM 生成，返回空报告提示")
        events.append(make_event("writer", "error", "无素材，已跳过 LLM 避免编造"))
    else:
        llm = None if state.get("mock") else get_llm("smart")
        if llm is not None:
            try:
                resp = llm.invoke(
                    _PROMPT.format(
                        topic=state["topic"],
                        days=state.get("days", 30),
                        opinions=_format_opinions(state),
                        materials=_format_materials(state),
                    )
                )
                report = getattr(resp, "content", "") or ""
            except Exception as e:  # noqa: BLE001
                logger.exception("writer LLM 调用失败，走模板降级")
                errors.append(f"writer: {e}")
                events.append(make_event("writer", "error", str(e)))

    if not report.strip():
        report = _mock_report(state)

    events.append(make_event("writer", "done", f"报告生成完毕（{len(report)} 字符）"))
    return {"report": report, "progress_events": events, "errors": errors}
