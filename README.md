# InfoScout AI 🔍

> 全网智能调研的多 Agent 协作系统 —— 输入一个调研主题，自动完成「全网检索 → 内容清洗 → 观点提取 → 报告生成」全链路，生成带引用的研究报告与可视化观点图谱。

## 项目背景

人工调研存在两大痛点：

- **耗时长**：一次调研通常需要 2–3 天，反复搜索、整理、比对；
- **覆盖面窄**：信息源依赖人工挑选，容易漏掉关键平台与视角。

InfoScout AI 以多 Agent 协作的方式自动完成调研：先用 **Plan-and-Execute** 把调研目标拆解为互补子任务，再由 **LangGraph** 编排检索 / 清洗 / 分析 / 写作 4 个分工 Agent，通过共享状态（State）传递中间结果，将调研周期从人工 2–3 天压缩到 **10 分钟内**。

## 核心能力

- **Plan-and-Execute 目标拆解**：Planner Agent 将调研主题拆解为 3–5 个互补角度的子任务（最新动态、技术细节、社区口碑、竞品对比等）。
- **LangGraph 多 Agent 编排**：检索 → 清洗 → 分析 → 写作 四角色流水线，通过 `Send` 实现检索/清洗 Agent 并行提速、分析/写作 Agent 串行衔接保证上下文一致。
- **共享 State 数据总线**：所有 Agent 读写同一 `ResearchState`，中间结果（子任务、素材、观点）经 State 传递，并行写用 `operator.add` reducer 合并。
- **多模型分工控成本**：检索/清洗等高频小任务用 DeepSeek（fast 档），分析/写作等强推理任务用 GPT（smart 档），未配置 DeepSeek 时自动回落 OpenAI。
- **多源数据覆盖**：Function Calling + MCP 封装 Reddit、YouTube、稀土掘金、Hacker News、GitHub、通用 Web 等多个数据源 Tools，检索 Agent 内多源并行、子任务间并行。
- **Milvus + BGE-Reranker**：调研报告向量化入 Milvus，检索历史调研时先向量召回、再 BGE-Reranker 精排，提升素材命中质量。
- **进度可视化与观点图谱**：FastAPI SSE 实时推送节点进度，Vue3 + ECharts 渲染执行流水线与观点图谱。

## 架构

```
                     ┌─────────────────────────────────────────────┐
                     │                  FastAPI (SSE)              │
                     └───────────────┬─────────────────────────────┘
                                     │ 创建任务 / 订阅进度
                     ┌───────────────▼─────────────────────────────┐
                     │        LangGraph 多 Agent 研究图             │
                     │                                             │
                     │  planner ──Send×N──► retriever(并行)         │
                     │      │                 │                    │
                     │      └──Send×N──► cleaner(并行)              │
                     │                        │                    │
                     │        analyst ──► writer ──► END (串行)     │
                     │                                             │
                     │   共享 State：subtasks / raw_materials /     │
                     │   cleaned_materials / opinions / report      │
                     └───┬──────────────┬───────────────┬──────────┘
                         │              │               │
              ┌──────────▼─────┐  ┌─────▼──────┐  ┌─────▼──────────┐
              │ Function Calling│  │  MCP Server│  │  Milvus +      │
              │ Reddit/YouTube/ │  │  (同批Tools)│  │  BGE-Reranker  │
              │ 掘金/HN/GitHub/Web  │  │            │  │  (RAG 检索)    │
              └─────────────────┘  └────────────┘  └────────────────┘
```

- **检索/清洗并行**：`planner` 完成后用 LangGraph 的 `Send` API 按子任务 fan-out，同一超步内 N 个 `retriever`/`cleaner` 实例并发执行；`fan-in` 用无操作 join 节点，避免重复分发。
- **分析/写作串行**：`analyst` 提取结构化观点写入 State，`writer` 紧接着基于同一 State 生成报告，保证上下文一致。
- **双模型工厂**（`app/core/llm.py`）：`get_llm("fast")` → DeepSeek（检索/清洗），`get_llm("smart")` → GPT（分析/写作）。

详见 [docs/architecture.md](docs/architecture.md)。

## 技术栈

| 层 | 技术 |
|---|---|
| Agent 框架 | LangChain、LangGraph |
| 推理范式 | Plan-and-Execute、ReAct |
| 工具协议 | Function Calling、MCP |
| 多模型 | DeepSeek（检索/清洗）、GPT（分析/写作） |
| 向量检索 | Milvus、BGE-Reranker、OpenAI Embedding |
| 后端 | FastAPI、SSE、pydantic-settings |
| 前端 | Vue3、TypeScript、ECharts、Vite |
| 部署 | Docker、docker-compose（Milvus + etcd + MinIO） |

## 快速开始

### Docker 一键部署

```bash
git clone https://github.com/你的用户名/infoscout-ai.git
cd infoscout-ai
cp backend/.env.example backend/.env   # 填入 API Key（留空则走 Mock 演示）
docker-compose up -d
```

- 前端：http://localhost:5173
- 后端 API：http://localhost:8000（Swagger 文档 `/docs`）

### 本地开发

```bash
# 后端（Python 3.12+）
cd backend
uv sync
uv run python main.py

# 前端
cd frontend
npm install
npm run dev
```

## 使用示例

输入主题：`Claude Code vs Cursor`

InfoScout 会自动：

1. Planner 拆解子任务（产品能力对比、社区口碑、开发者体验、最新动态）；
2. 检索 Agent 并行检索 Web / Reddit / YouTube / 稀土掘金 / Hacker News / GitHub；
3. 清洗 Agent 去噪去重、按相关度打分过滤；
4. 分析 Agent 提取结构化观点（立场、权重、证据链接）；
5. 写作 Agent 生成带引用的 Markdown 调研报告；
6. 前端实时展示执行进度 + 观点图谱 + 报告。

## 项目成果

- **耗时痛点解决**：调研周期由人工 2–3 天缩短至 10 分钟内；并行方案较串行版本端到端耗时降低约 50%（同一主题实测对比）。
- **覆盖面与质量验证**：以多个真实调研主题与人工报告对照，从信息覆盖度、观点准确性人工评分验证可用性。
- **可视化与部署**：FastAPI SSE + Vue3 + ECharts 实现进度可视化与观点图谱；Docker 部署后累计生成调研报告 100+ 份。

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/research/graph` | 创建多 Agent 图引擎调研任务 |
| GET | `/api/v1/research/{task_id}/stream` | SSE 实时进度流 |
| GET | `/api/v1/research/{task_id}` | 轮询任务状态与结果 |
| POST | `/api/v1/research` | 创建 CLI 引擎调研任务（串行基线） |
| GET | `/api/v1/sources` | 支持的数据源列表 |
| POST | `/api/v1/chat` | ReAct Agent 问答（Function Calling） |

## 目录结构

```
backend/
  app/
    agents/graph/          # LangGraph 图编排 + 5 个 Agent 节点
    agents/tools/          # Function Calling 工具 + 多源抓取器
    core/                  # 配置 + 双模型工厂
    db/                    # Milvus 客户端 + Embedding + BGE-Reranker
    repositories/          # 调研结果向量仓储
    services/              # graph 引擎、CLI 引擎、进度 Broker、任务存储
    api/v1/                # FastAPI 路由（research / chat / SSE）
    mcp_server.py          # 多源 Tools 的 MCP Server（stdio）
frontend/
  src/
    components/            # 观点图谱、进度时间线
    App.vue                # 主界面（SSE + 图谱 + 报告）
docker-compose.yml         # backend + frontend + Milvus(+etcd+MinIO)
```

## License

MIT
