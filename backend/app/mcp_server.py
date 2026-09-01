"""InfoScout 多源数据源 MCP Server —— 把 Web（必应中国）/ 稀土掘金 / B站 / 思否 /
Reddit / YouTube / Hacker News / GitHub 等数据源工具以 MCP（Model Context Protocol）方式
暴露给外部 Agent（Claude Desktop 等）。

与 Function Calling（LangChain @tool，见 app/agents/tools/source_tools.py）
共用同一批底层抓取函数，保证两种协议行为一致。

境内可达源（web/juejin/bilibili/segmentfault）在纯国内网络即可用；
外网源（reddit/youtube/hackernews/github）需要能访问外网的环境。

启动（stdio）：
    python -m app.mcp_server

依赖：pip install mcp（可选，未安装时本模块不会影响 FastAPI 主程序）。
"""
from __future__ import annotations

from app.agents.tools.sources import (
    search_bilibili,
    search_github,
    search_hackernews,
    search_juejin,
    search_reddit,
    search_segmentfault,
    search_web,
    search_youtube,
)


def build_mcp():
    """惰性导入 FastMCP 并注册数据源工具，返回 server 实例。"""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:  # pragma: no cover
        raise SystemExit("MCP 未安装，请先执行：pip install mcp") from e

    server = FastMCP("infoscout-sources")

    @server.tool()
    def search_web(query: str, count: int = 5) -> list[dict]:
        """通用网页检索（必应中国，免 Key，境内可用），返回网页结果列表。"""
        return search_web(query, count)

    @server.tool()
    def search_juejin(query: str, count: int = 5) -> list[dict]:
        """检索稀土掘金（juejin.cn）上关于某主题的文章，返回文章列表。

        适合获取中文技术社区的观点、教程与实践经验（境内可达）。
        """
        return search_juejin(query, count)

    @server.tool()
    def search_bilibili(query: str, count: int = 5) -> list[dict]:
        """检索 B站（bilibili.com）上关于某主题的视频，返回视频列表。

        适合获取中文视频测评、教程与观点（境内可达）。
        """
        return search_bilibili(query, count)

    @server.tool()
    def search_segmentfault(query: str, count: int = 5) -> list[dict]:
        """检索思否（segmentfault.com）上关于某主题的技术文章/问答，返回列表。

        适合获取中文技术社区的问答与经验交流（境内可达）。
        """
        return search_segmentfault(query, count)

    @server.tool()
    def search_reddit(query: str, count: int = 5) -> list[dict]:
        """检索 Reddit 上关于某主题的讨论，返回帖子列表（需能访问外网）。"""
        return search_reddit(query, count)

    @server.tool()
    def search_youtube(query: str, count: int = 5) -> list[dict]:
        """检索 YouTube 上关于某主题的视频，返回视频列表（需能访问外网）。"""
        return search_youtube(query, count)

    @server.tool()
    def search_hackernews(query: str, count: int = 5) -> list[dict]:
        """检索 Hacker News 上关于某主题的讨论/文章，返回列表（需能访问外网）。"""
        return search_hackernews(query, count)

    @server.tool()
    def search_github(query: str, count: int = 5) -> list[dict]:
        """检索 GitHub 上关于某主题的仓库，返回仓库列表（需能访问外网）。"""
        return search_github(query, count)

    return server


def main() -> None:
    """stdio 方式启动 MCP server。"""
    build_mcp().run()


if __name__ == "__main__":
    main()
