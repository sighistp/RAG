# RAGv3 部署指南

## 方式一：Docker 部署（推荐）

### 对方需要做的

```bash
# 1. 安装 Docker（如果没装）
# Windows: https://docs.docker.com/desktop/install/windows-install/
# Linux: curl -fsSL https://get.docker.com | sh

# 2. 克隆项目
git clone <你的仓库地址> RAGv3
cd RAGv3

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key

# 4. 一键启动
docker-compose up -d

# 5. 访问
# http://localhost:8000
```

### 你自己需要做的（首次打包）

```bash
# 在项目根目录执行
docker-compose build
docker-compose up -d
```

### 数据持久化

`./data` 目录挂载为 Docker 卷，包含：
- `data/users.db` — 用户数据库
- `data/upload/` — 上传的文件
- `data/qdrant/` — 向量数据库
- `data/analysis.db` — 分析数据库

---

## 方式二：直接部署到 Linux 服务器

### 1. 服务器准备

```bash
# SSH 登录服务器
ssh root@你的服务器IP

# 安装 Python 3.12
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip

# 安装 Node.js 20（构建前端用）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2. 上传代码

```bash
# 方式A: git clone
git clone <你的仓库地址> /opt/RAGv3

# 方式B: scp 上传
scp -r ./RAGv3 root@服务器IP:/opt/RAGv3
```

### 3. 构建前端

```bash
cd /opt/RAGv3/frontend
npm ci
npm run build
# 产物会输出到 /opt/RAGv3/static/
```

### 4. 安装后端依赖

```bash
cd /opt/RAGv3
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. 配置环境变量

```bash
cp .env.example .env
nano .env
# 填入 API Key 等配置
```

### 6. 启动服务

```bash
# 测试启动
python -m uvicorn rag.api:app --host 0.0.0.0 --port 8000

# 正式运行（用 systemd 管理）
```

### 7. 配置 systemd 服务（开机自启）

```bash
cat > /etc/systemd/system/ragv3.service << 'EOF'
[Unit]
Description=RAGv3 Knowledge Base System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/RAGv3
ExecStart=/opt/RAGv3/venv/bin/python -m uvicorn rag.api:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
EnvironmentFile=/opt/RAGv3/.env

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ragv3
systemctl start ragv3
```

### 8. 配置 Nginx 反向代理（可选，支持域名 + HTTPS）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 流式响应需要这些
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

---

## 方式三：云平台部署

### Railway（最简单）

1. 注册 https://railway.app
2. 连接 GitHub 仓库
3. 设置环境变量（.env 里的内容）
4. 自动部署，获得一个公网域名

### Zeabur（国内友好）

1. 注册 https://zeabur.com
2. 导入 GitHub 仓库
3. 配置环境变量
4. 自动部署

### 注意事项

- 云平台免费额度有限，向量数据库可能需要外部托管
- SQLite 文件在容器重启后会丢失，需要挂载持久化卷
- 推荐用 Docker 部署到自己的服务器

---

## 部署后检查清单

- [ ] `http://你的IP:8000` 能访问
- [ ] `http://你的IP:8000/health` 返回正常
- [ ] 注册用户功能正常
- [ ] 上传文件功能正常
- [ ] 对话功能正常（流式响应）
- [ ] 设置了 `INIT_ADMIN_USERNAME` 环境变量
