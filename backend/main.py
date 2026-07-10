"""
InfoScout AI 后端启动入口（薄入口）。

业务代码已迁至 app/ 包，此文件仅负责 uvicorn 启动。
启动命令：python main.py
"""
from __future__ import annotations

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
