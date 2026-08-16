"""
调研服务：封装 last30days CLI 调用。

这是本项目的核心业务逻辑层（对应 SpringBoot 的 @Service）。
后端本身不做检索，而是起子进程调用 skills/last30days/scripts/last30days.py。
提供异步（HTTP 路由用）与同步（LangChain tool 用）两个入口。
"""
from __future__ import annotations

import asyncio
import os
import subprocess

from app.core.config import CLI_ENTRY, SCRIPTS_DIR, get_settings
from app.schemas.research import ResearchRequest
from app.services.task_store import TaskStore


def build_command(req: ResearchRequest) -> list[str]:
    """根据请求构建 CLI 命令。"""
    cmd: list[str] = [
        "python",
        str(CLI_ENTRY),
        req.topic,
        "--emit",
        req.emit,
        "--days",
        str(req.days),
    ]
    # mock 模式下不加 --quick/--deep/--search（与 mock 组合会卡死，引擎 bug）
    if req.mock:
        cmd.append("--mock")
    else:
        if req.quick:
            cmd.append("--quick")
        if req.deep:
            cmd.append("--deep")
        if req.sources:
            cmd.extend(["--search", req.sources])
    return cmd


def _build_env() -> dict[str, str]:
    """构造子进程环境变量：继承当前环境 + 注入 .env 里的 Web 搜索 Key。

    pydantic-settings 读 .env 后不会回写到 os.environ，而 last30days CLI
    通过 os.environ 读 Key，所以这里显式注入。
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS_DIR)
    s = get_settings()
    # 只在 .env 配置了 Key 时才注入，避免覆盖宿主已有的值
    if s.brave_api_key:
        env["BRAVE_API_KEY"] = s.brave_api_key
    if s.exa_api_key:
        env["EXA_API_KEY"] = s.exa_api_key
    if s.serper_api_key:
        env["SERPER_API_KEY"] = s.serper_api_key
    return env


async def run_research_async(task_id: str, req: ResearchRequest, store: TaskStore) -> None:
    """异步执行调研任务（供 HTTP 路由调用，不阻塞事件循环）。"""
    store.update(task_id, status="running")

    cmd = build_command(req)
    store.update(task_id, cmd=cmd)

    env = _build_env()

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(SCRIPTS_DIR),
            env=env,
        )
        # 超时（默认 600s，可经 RESEARCH_TIMEOUT_SECONDS 覆盖）。
        # last30days 真实模式是多平台深度爬取，1-3 分钟正常，Reddit 等慢源更久。
        timeout = get_settings().research_timeout_seconds
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            store.update(
                task_id,
                status="failed",
                error=(
                    f"调研超时（{timeout}秒）—last30days 引擎未在限定时间内完成。"
                    "建议：改用多 Agent 图引擎（Reddit/YouTube/掘金等源更快）、"
                    "减少数据源、缩短天数，或用 Mock 模式。"
                ),
            )
            return
        rc = proc.returncode
        out_text = stdout.decode("utf-8", errors="replace")
        err_text = stderr.decode("utf-8", errors="replace")

        store.update(task_id, returncode=rc, stderr_tail=err_text[-1500:])

        if rc != 0:
            store.update(
                task_id,
                status="failed",
                error=err_text[-2000:] or f"exit code {rc} (无 stderr 输出)",
            )
        else:
            store.update(task_id, status="done", output=out_text)

    except Exception as e:  # noqa: BLE001
        store.update(task_id, status="failed", error=str(e))


def run_research_sync(
    topic: str,
    mock: bool = True,
    days: int = 30,
    emit: str = "md",
) -> str:
    """同步执行调研（供 LangChain tool 调用，阻塞直到完成）。"""
    settings = get_settings()
    cmd = ["python", str(CLI_ENTRY), topic, "--emit", emit, "--days", str(days)]
    if mock:
        cmd.append("--mock")

    env = _build_env()

    result = subprocess.run(
        cmd,
        capture_output=True,
        cwd=str(SCRIPTS_DIR),
        env=env,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        tail = (result.stderr or "")[-500:]
        return f"调研失败（exit {result.returncode}）: {tail}"
    return result.stdout or ""
