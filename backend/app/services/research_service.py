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
    if req.quick:
        cmd.append("--quick")
    if req.deep:
        cmd.append("--deep")
    if req.mock:
        cmd.append("--mock")
    if req.sources:
        cmd.extend(["--search", req.sources])
    return cmd


async def run_research_async(task_id: str, req: ResearchRequest, store: TaskStore) -> None:
    """异步执行调研任务（供 HTTP 路由调用，不阻塞事件循环）。"""
    store.update(task_id, status="running")

    cmd = build_command(req)
    store.update(task_id, cmd=cmd)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS_DIR)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(SCRIPTS_DIR),
            env=env,
        )
        stdout, stderr = await proc.communicate()
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

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS_DIR)

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
