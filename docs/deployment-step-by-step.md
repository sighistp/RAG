# RAGv3 完整部署教程（从零开始）

> 目标：像正常网站一样，别人打开链接就能用。

---

## 第一步：买服务器

### 推荐配置

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 2 核 | 2-4 核 |
| 内存 | 2 GB | 4 GB |
| 硬盘 | 40 GB | 50-100 GB |
| 带宽 | 1 Mbps | 3-5 Mbps |
| 系统 | Ubuntu 22.04 | Ubuntu 22.04/24.04 |
| 价格 | ~50 元/月 | ~80-100 元/月 |

### 购买推荐（国内）

| 平台 | 入口 | 说明 |
|------|------|------|
| 阿里云 | https://www.aliyun.com/product/swas | 轻量应用服务器，新用户有优惠 |
| 腾讯云 | https://cloud.tencent.com/product/lighthouse | 轻量应用服务器，学生有优惠 |
| 华为云 | https://www.huaweicloud.com/product/ecs.html | 弹性云服务器 |

> **新用户优惠**：阿里云/腾讯云新用户首年 50-100 元就能买到 2核2G 的服务器。

### 购买时选择

- 地域：选离你最近的（如华东-上海、华南-广州）
- 系统：**Ubuntu 22.04 LTS**
- 设置 root 密码（记下来！）

---

## 第二步：买域名（可选但推荐）

没有域名也能用，通过 `http://服务器IP:8000` 访问。
有域名的话可以绑域名 + HTTPS，更专业。

| 平台 | 入口 | 价格 |
|------|------|------|
| 阿里云万网 | https://wanwang.aliyun.com | .com 约 60 元/年 |
| 腾讯云 DNSPod | https://dnspod.cloud.tencent.com | .com 约 55 元/年 |

> **便宜的域名**：`.top` 域名首年约 10 元，`.xyz` 约 15 元。

购买后需要**域名备案**（国内服务器必须），阿里云/腾讯云有免费备案服务，大约 1-2 周。

---

## 第三步：连接服务器

### Windows 用户

1. 下载 [MobaXterm](https://mobaxterm.mobatek.net/)（免费）或用 Windows 自带的 PowerShell
2. 打开终端，输入：

```bash
ssh root@你的服务器IP
```

3. 输入密码，连接成功

### Mac 用户

打开终端，输入：

```bash
ssh root@你的服务器IP
```

---

## 第四步：上传代码

### 方式 A：用 Git（推荐）

```bash
# 服务器上安装 git
apt update && apt install -y git

# 克隆项目（替换成你的仓库地址）
cd /opt
git clone https://github.com/<你的用户名>/RAGv3.git
```

### 方式 B：用 scp 上传（不需要 Git）

在你自己的电脑上执行：

```bash
# 在项目根目录执行
scp -r . root@你的服务器IP:/opt/RAGv3
```

### 方式 C：用 MobaXterm（最简单）

1. 打开 MobaXterm，连接服务器
2. 左侧有文件浏览器
3. 直接把项目文件夹拖到 `/opt/` 目录

---

## 第五步：配置环境变量

```bash
cd /opt/RAGv3
cp .env.example .env
nano .env
```

在 nano 编辑器中：
- 修改 `RAG_DEEPSEEK_API_KEY=你的key`
- 修改 `RAG_BAILIAN_API_KEY=你的key`
- 按 `Ctrl+O` 保存，`Ctrl+X` 退出

---

## 第六步：一键部署

```bash
cd /opt/RAGv3
bash deploy.sh
```

等待 2-5 分钟（首次需要构建 Docker 镜像），完成后会显示访问地址。

---

## 第七步：配置域名和 HTTPS（可选）

### 7.1 域名解析

在域名管理后台，添加 A 记录：
- 主机记录：`@`（或 `www`）
- 记录值：你的服务器 IP

### 7.2 安装 Nginx + 申请免费 HTTPS 证书

```bash
# 安装 Nginx 和 Certbot
apt install -y nginx certbot python3-certbot-nginx

# 配置 Nginx
cat > /etc/nginx/sites-available/ragv3 << 'EOF'
server {
    server_name your-domain.com;  # 改成你的域名

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 流式响应必须关闭缓冲
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
EOF

# 启用配置
ln -sf /etc/nginx/sites-available/ragv3 /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 申请免费 HTTPS 证书（需要域名已解析到此 IP）
certbot --nginx -d your-domain.com
```

申请成功后，访问 `https://your-domain.com` 即可。

证书会自动续期，无需手动管理。

---

## 部署后维护

### 常用命令

```bash
# 查看服务状态
docker compose -f /opt/RAGv3/docker-compose.yml ps

# 查看日志
docker compose -f /opt/RAGv3/docker-compose.yml logs -f

# 重启服务
docker compose -f /opt/RAGv3/docker-compose.yml restart

# 停止服务
docker compose -f /opt/RAGv3/docker-compose.yml down

# 更新代码后重新部署
cd /opt/RAGv3
git pull
docker compose build --no-cache
docker compose up -d
```

### 数据备份

重要数据在 `/opt/RAGv3/data/` 目录下，定期备份：

```bash
# 手动备份
tar czf /tmp/ragv3-backup-$(date +%Y%m%d).tar.gz /opt/RAGv3/data/

# 设置自动备份（每天凌晨 3 点）
echo "0 3 * * * tar czf /tmp/ragv3-backup-\$(date +\%Y\%m\%d).tar.gz /opt/RAGv3/data/" | crontab -
```

---

## 完整流程总结

```
买服务器 → SSH 连接 → 上传代码 → 配置 .env → bash deploy.sh → 完成！
                                                          ↓
                                              http://服务器IP:8000
                                                          ↓
                                              （可选）绑域名 + HTTPS
                                                          ↓
                                              https://your-domain.com
```

别人只需要打开链接就能用了。
