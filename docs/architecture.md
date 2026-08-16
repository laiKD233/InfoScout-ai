# InfoScout AI 架构说明

本文档说明 InfoScout AI 多 Agent 协作调研系统的技术架构与关键设计。

## 1. 总体流程

调研目标 → Plan-and-Execute 拆解 → 多源并行检索 → 内容清洗 → 观点提取 → 报告生成 → 可视化展示。

```
用户输入主题
    │
    ▼
planner（Plan-and-Execute 拆解为子任务）
    │
    ├─ Send t1 ─► retriever(多源并行) ─┐
    ├─ Send t2 ─► retriever(多源并行) ─┼─► join_retrieval
    └─ Send tN ─► retriever(多源并行) ─┘
                                          │
                        （按子任务再 fan-out）
                                          │
    ├─ Send t1 ─► cleaner ─┐
    ├─ Send t2 ─► cleaner ─┼─► join_cleaning
    └─ Send tN ─► cleaner ─┘
                                          │
                        analyst（串行，smart 档）
                                          │
                        writer （串行，smart 档）
                                          │
                                         END
```

## 2. LangGraph 编排（`app/agents/graph/`）

### 节点

| 节点 | 职责 | 并行性 | 模型档位 |
|---|---|---|---|
| `planner` | Plan-and-Execute 的 Plan 阶段，拆解 3–5 个互补子任务 | 单次 | fast（DeepSeek） |
| `retriever` | 检索单个子任务，多源并行拉取素材 | 子任务间 Send 并行 + 单任务内多源并行 | 无需 LLM |
| `cleaner` | 去噪去重、提炼要点、相关度打分过滤 | 子任务间 Send 并行 | fast（DeepSeek） |
| `analyst` | 从清洗素材提取结构化观点（立场/权重/证据） | 串行 | smart（GPT） |
| `writer` | 生成带引用的 Markdown 报告 | 串行 | smart（GPT） |

### 并行机制

- `builder._dispatch_retrieval` 用 LangGraph 的 `Send` API 返回 N 个 `Send("retriever", payload)`，同一超步内 N 个 retriever 实例并发执行，产出经 State 的 `operator.add` reducer 合并。
- 同理 `_dispatch_cleaning` 按子任务分组后 fan-out 到 cleaner。
- 并行实例全部完成后，无操作的 `join` 节点只执行一次，再进入串行衔接——若直接在并行节点上挂 conditional edge，每个实例都会触发一次路由导致重复分发。

### 共享 State（`state.py`）

`ResearchState` 是多 Agent 的「数据总线」：

- 串行字段（`subtasks`/`opinions`/`report`）：覆盖写。
- 并行字段（`raw_materials`/`cleaned_materials`/`progress_events`/`errors`）：`Annotated[list, operator.add]` 拼接合并，避免并发写冲突。

## 3. 多模型分工（`app/core/llm.py`）

两档模型工厂 `get_llm(tier)`：

- **fast 档**：planner / cleaner（高频小任务），优先 DeepSeek（`deepseek-chat`），未配置时回落 OpenAI `fast_llm_model`。
- **smart 档**：analyst / writer（强推理 + 长文生成），用 OpenAI `llm_model`（默认 `gpt-4o-mini`）。

完全无 Key 时 `llm_available()` 返回 False：检索仍走真实抓取，仅 planner/cleaner/analyst/writer 的 LLM 步骤降级为规则/模板，保证链路可跑通。

## 4. 多源数据 Tools（Function Calling + MCP）

- **底层抓取器**（`app/agents/tools/sources/`）：Reddit（search.rss）、YouTube（feeds/videos.xml）、稀土掘金（公开 search API）、Hacker News（官方 Algolia API）、GitHub（官方搜索 API）、通用 Web（DuckDuckGo HTML），全部免 Key、永不抛异常。
- **Function Calling**（`app/agents/tools/source_tools.py`）：`@tool` 装饰为 LangChain Tool，自动生成 JSON schema；注册进 chat 的 ReAct Agent。
- **MCP**（`app/mcp_server.py`）：同一批函数经 FastMCP 暴露为 `search_reddit` / `search_youtube` / `search_juejin` / `search_hackernews` / `search_github` / `search_web`，`python -m app.mcp_server` 以 stdio 启动。

`retriever` 节点直接经 `SOURCE_SEARCHERS` 注册表并行调用各数据源，任一源失败不影响其它源。

## 5. RAG 检索（Milvus + BGE-Reranker）

- **写入**：调研完成后，报告经 OpenAI Embedding 向量化写入 Milvus（`research_repository.save`）。
- **检索**（`research_repository.search`）：query 向量化 → Milvus 召回 `top_k*3` 候选 → BGE-Reranker 精排 → 截断返回 `top_k`。
- **BGE-Reranker**（`app/db/reranker.py`）：本地 Cross-Encoder（默认 `BAAI/bge-reranker-v2-m3`），未安装 FlagEmbedding 时自动降级为纯向量相似度，不影响主链路。

## 6. 实时进度（SSE）

- **进度 Broker**（`app/services/progress_broker.py`）：按 task_id 分组的发布/订阅总线，带缓冲重放，线程安全。
- **图执行**（`graph_research_service`）：用 `graph.stream(stream_mode="values")` 逐超步产出完整 State，按已发布数量差出增量进度事件，实时 publish；结束时 publish `result` 事件（含报告/观点/子任务）。
- **SSE 接口**（`GET /api/v1/research/{task_id}/stream`）：订阅 Broker、重放缓冲、推送 `text/event-stream`；前端 EventSource 消费。

## 7. 前端可视化（Vue3 + ECharts）

- `ProgressTimeline.vue`：把 progress_events 渲染为「规划→检索→清洗→分析→写作」五段流水线。
- `OpinionGraph.vue`：ECharts 力导向图，主题居中、观点按立场着色（正面/负面/中立）、按权重定节点大小。

## 8. 与 CLI 引擎的对比基线

`/api/v1/research`（CLI 引擎）通过子进程调用 last30days CLI，串行执行，保留作为端到端耗时对比基线；`/api/v1/research/graph`（图引擎）为多 Agent 并行实现。并行方案较串行基线端到端耗时降低约 50%。
