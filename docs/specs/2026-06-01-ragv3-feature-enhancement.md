# RAGv3 功能增强设计文档

> **日期：** 2026-06-01
> **状态：** 待审批
> **范围：** RAGv3 用户端功能增强（用户系统 + 文件管理 + 对话历史 + 反馈）

---

## 1. 背景与目标

### 现状

RAGv3 当前是一个单用户、无登录的系统：
- 文件只能通过管理员放到 `data/upload/` 目录
- 对话历史刷新页面即丢失
- 无用户身份识别
- 无反馈机制

### 目标

将 RAGv3 升级为多用户、有状态的系统：
- 用户注册/登录，个人数据隔离
- 对话历史持久化，支持新建对话
- 用户可上传/删除文件
- 反馈按钮记录满意度

### 非目标

- 不做权限分级（所有用户平等）
- 不做文件权限控制（所有用户可见所有文件）
- 不做流式输出（后续优化）

---

## 2. 架构

```
┌─────────────────────────────────────────┐
│           Web 前端 (index.html)          │
│  登录/注册 → 文件管理 → 聊天 → 反馈      │
└──────────────┬──────────────────────────┘
               │ fetch()
┌──────────────▼──────────────────────────┐
│           FastAPI (api.py)               │
│  /register  /login  /files  /query      │
│  /upload  /delete  /feedback            │
│  /conversations  /conversations/{id}    │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         SQLite (ragv3.db)               │
│  users 表 | conversations 表            │
│  messages 表 | feedback 表              │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│       RAG Pipeline (Qdrant + BM25)      │
│  retriever → reranker → generator       │
└─────────────────────────────────────────┘
```

---

## 3. 数据模型

### 3.1 users 表

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
```

- 密码用 `hashlib.pbkdf2_hmac` 加盐哈希（不存明文）
- 用户名唯一

### 3.2 conversations 表

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT DEFAULT '新对话',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

- 每个用户可有多个对话
- `title` 默认"新对话"，可用第一条消息自动更新

### 3.3 messages 表（扩展现有）

```sql
-- 现有 DialogueMemory 的 messages 表，增加 conversation_id
ALTER TABLE messages ADD COLUMN conversation_id INTEGER;
ALTER TABLE messages ADD COLUMN user_id INTEGER;
```

或新建独立表：

```sql
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,  -- 'user' 或 'assistant'
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```

### 3.4 feedback 表

```sql
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    value TEXT NOT NULL,  -- 'positive' 或 'negative'
    comment TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (message_id) REFERENCES chat_messages(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## 4. API 端点

### 4.1 用户系统

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/register` | 注册（username + password） | 无 |
| POST | `/login` | 登录，返回 token | 无 |
| GET | `/me` | 获取当前用户信息 | 需要 |

**认证方式：** JWT token（`python-jose` 库），登录后返回 token，前端存 localStorage，每次请求带 `Authorization: Bearer {token}`。

### 4.2 对话管理

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/conversations` | 列出当前用户的所有对话 | 需要 |
| POST | `/conversations` | 新建对话 | 需要 |
| DELETE | `/conversations/{id}` | 删除对话及其消息 | 需要 |
| GET | `/conversations/{id}/messages` | 获取对话的消息历史 | 需要 |

### 4.3 查询（扩展现有）

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/query` | 查询（增加 conversation_id 参数） | 需要 |

**改动：** `QueryRequest` 增加 `conversation_id` 字段，查询后自动保存消息到 `chat_messages` 表。

### 4.4 文件管理（扩展现有）

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/upload` | 上传文件并索引 | 需要 |
| DELETE | `/files/{filename}` | 删除文件及索引 | 需要 |
| GET | `/files` | 列出文件 | 无 |

### 4.5 反馈

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/feedback` | 提交反馈（message_id + value） | 需要 |

---

## 5. 前端改动

### 5.1 登录/注册页

- 打开页面时检查 localStorage 有无 token
- 无 token → 显示登录/注册表单
- 有 token → 验证有效性，有效则进入主页

### 5.2 侧边栏（对话列表）

- 左侧新增侧边栏，显示对话列表
- "新建对话"按钮
- 点击对话切换历史
- 删除对话按钮

### 5.3 文件管理增强

- 文件卡片增加删除按钮（×）
- 文件选择器区域增加"上传文件"按钮
- 支持拖拽上传

### 5.4 反馈按钮

- 每个 AI 回答下方显示 👍👎
- 点击后记录到数据库
- 已反馈的显示高亮状态

---

## 6. 安全设计

| 措施 | 说明 |
|------|------|
| 密码哈希 | `hashlib.pbkdf2_hmac` + 随机盐 |
| JWT 过期 | token 24 小时过期 |
| 输入校验 | 用户名 3-20 字符，密码 6+ 字符 |
| SQL 注入 | 参数化查询（已有） |
| 文件大小 | 10MB 限制（已有） |
| 文件格式 | 白名单校验（已有） |

---

## 7. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `rag/auth.py` | 修改 | 新增 JWT 认证 + 注册/登录逻辑 |
| `rag/api.py` | 修改 | 新增用户/对话/反馈端点，改造 /query |
| `rag/memory.py` | 修改 | 支持 conversation_id |
| `static/index.html` | 修改 | 登录页 + 侧边栏 + 上传 + 反馈 |
| `requirements.txt` | 修改 | 新增 `python-jose`, `passlib` |
| `tests/test_auth.py` | 新建 | 用户系统测试 |
| `tests/test_conversations.py` | 新建 | 对话管理测试 |

---

## 8. 实现步骤（TDD）

| 步骤 | 内容 | 测试 |
|------|------|------|
| 1 | SQLite 用户表 + 注册/登录 API | 6 个测试 |
| 2 | JWT 认证中间件 | 4 个测试 |
| 3 | 对话管理 API（CRUD） | 5 个测试 |
| 4 | /query 改造（保存消息到 chat_messages） | 3 个测试 |
| 5 | 文件上传/删除 API | 4 个测试 |
| 6 | 反馈 API | 3 个测试 |
| 7 | 前端改造（登录 + 侧边栏 + 上传 + 反馈） | 手动测试 |
| 8 | 全量回归 | 215+ 测试 |

---

## 9. 验收标准

1. 用户能注册账号并登录
2. 登录后能新建对话、切换对话、删除对话
3. 对话历史持久化（刷新页面不丢失）
4. 用户能通过前端上传文件（拖拽/按钮）
5. 用户能删除已有文件
6. 每个回答有 👍👎 反馈按钮
7. 不同用户的数据互相隔离
8. 215+ 后端测试全过
