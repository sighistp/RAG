# ── Stage 1: 构建前端 ──────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ── Stage 2: 运行后端 ─────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# 系统依赖：build-essential (编译) + default-jre-headless (PDF 解析)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Java 环境变量
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# 标记 Docker 环境（start.py 根据此变量决定监听地址）
ENV DOCKER_CONTAINER=1

# Python 依赖
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 项目代码
COPY . .

# 前端静态文件（从 Stage 1 复制）
COPY --from=frontend-builder /app/static /app/static

# 数据目录（运行时挂载卷）
RUN mkdir -p /app/data/upload /app/qdrant_data

# 暴露端口
EXPOSE 8000

# 启动（用 start.py 包含自动索引逻辑）
CMD ["python", "start.py"]
