# InfoScout-ai
InfoScout AI — 全网智能调研 Agent，输入主题自动检索 Reddit/X/YouTube/博客等多平台，生成带引用的研究简报。Built with LangGraph + MCP + RAG.


# InfoScout AI 🔍

> 全网智能调研 Agent — 输入一个主题，自动检索 Reddit、X、YouTube、Hacker News、技术博客等 10+ 平台，按热度与相关性聚类去重，生成带引用的研究简报。

## ✨ 核心能力

- **多平台并行检索**：覆盖 Reddit、X、YouTube、Hacker News、GitHub、技术博客等 10+ 数据源
- **智能主题解析**：输入主题自动识别相关实体（人物、项目、社区），避免关键词搜索遗漏
- **跨平台事件聚类**：同一事件多来源自动合并去重，去重率约 60%
- **热度排序**：按点赞、评论、观看量综合排序，突出真实社区关注度
- **多智能体协作**：检索 → 清洗 → 分析 → 写作，LangGraph 编排四角色工作流
- **报告生成**：输出带引用的结构化研究报告 + 可视化观点图谱

## 🛠 技术栈

- **Agent 框架**：LangChain、LangGraph
- **推理范式**：ReAct、Plan-and-Execute
- **工具协议**：Function Calling、MCP
- **爬取**：Playwright（动态渲染与反爬）
- **RAG**：Milvus、BGE-Reranker、GraphRAG
- **大模型**：OpenAI API、DeepSeek API（多模型协同）
- **后端**：FastAPI
- **前端**：Vue3、TypeScript、ECharts
- **部署**：Docker

## 🚀 快速开始

```bash
git clone https://github.com/你的用户名/infoscout-ai.git
cd infoscout-ai
docker-compose up -d
```

访问 http://localhost:8000 即可使用

## 📖 使用示例

输入主题：`Claude Code vs Cursor`

InfoScout 会自动：
1. 解析相关实体（Anthropic、Cursor 官方、开发者社区）
2. 并行检索 Reddit、X、YouTube、Hacker News 等
3. 聚类去重，按热度排序
4. 生成对比研究报告

## 🏗 架构
