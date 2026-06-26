#!/bin/bash
# 部署脚本：拉取最新代码 + 强制重建（避免缓存问题）
set -e

cd "$(dirname "$0")/.."

echo "=== 拉取最新代码 ==="
git pull

echo "=== 强制重建（--no-cache）==="
docker compose build --no-cache rag-app

echo "=== 启动容器 ==="
docker compose up -d

echo "=== 部署完成 ==="
docker logs ragv3 2>&1 | tail -5
