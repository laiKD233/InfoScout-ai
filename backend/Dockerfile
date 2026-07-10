FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（yt-dlp 用于 YouTube 转录）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端应用包
COPY backend/app ./app
COPY backend/main.py .

# 复制 last30days 引擎
COPY skills/ ./skills/

# 创建结果目录
RUN mkdir -p /app/results

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
