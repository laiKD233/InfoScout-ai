FROM python:3.12-slim

WORKDIR /app

# 安装 uv（从官方镜像拷贝二进制，无需 pip 安装）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 安装系统依赖（yt-dlp 用于 YouTube 转录）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖清单，利用 Docker layer 缓存（依赖变动少时跳过后续重装）
COPY backend/pyproject.toml backend/uv.lock ./

# 安装 Python 依赖到 .venv
#   --frozen              按 uv.lock 锁定版本安装，不重新解析
#   --no-dev              不安装 dev 依赖组（pytest/httpx）
#   --no-install-project  不安装项目本身（backend 是应用，非库）
RUN uv sync --frozen --no-dev --no-install-project

# 复制后端应用包
COPY backend/app ./app
COPY backend/main.py ./

# 复制 last30days 引擎（backend 通过 subprocess 调用）
COPY skills/ ./skills/

# 创建结果目录
RUN mkdir -p /app/results

# 将 venv 加入 PATH，直接用 uvicorn 启动
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
