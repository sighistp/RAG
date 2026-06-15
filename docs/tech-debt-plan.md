# RAGv3 技术债修复设计

> **日期：** 2026-06-12
> **状态：** 待审批
> **范围：** BM25 持久化 + SQLite 统一目录 + JWT secret 持久化 + 前端组件化

---

## 1. BM25 持久化（SQLite 倒排索引）

### 问题

`retriever.py` 每次查询都调用 `_load_all_chunks()` 从 Qdrant 全量加载 chunks 构建 BM25 索引。数据量大时（>1000 chunks）是性能瓶颈。

### 方案

用 SQLite 存储倒排索引，索引文档时构建并持久化，查询时直接加载。

### 数据模型

```sql
-- data/bm25_index.db
CREATE TABLE IF NOT EXISTS bm25_terms (
    term TEXT NOT NULL,
    chunk_id INTEGER NOT NULL,
    doc_name TEXT NOT NULL,
    tf REAL NOT NULL,           -- 词频
    chunk_text TEXT NOT NULL,   -- 原始文本（用于检索）
    PRIMARY KEY (term, chunk_id)
);

CREATE TABLE IF NOT EXISTS bm25_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- 存储 avgdl、total_chunks 等元数据
```

### 工作流程

```
索引时：
  chunks → jieba 分词 → 计算 TF → 写入 SQLite bm25_terms 表
  同时构建内存 BM25 索引（用于当次查询）

查询时：
  1. 检查 bm25_index.db 是否存在且有效
  2. 有效 → 直接从 SQLite 加载倒排索引构建 BM25
  3. 无效 → 从 Qdrant 全量加载 + 构建 + 持久化

更新时：
  新文档索引 → 增量更新 bm25_terms 表（不重建）
  删除文档 → 删除对应 chunk_id 的条目
```

### 文件变更

| 文件 | 改动 |
|------|------|
| `rag/bm25_store.py` | 新建 — SQLite 倒排索引存储 |
| `rag/retriever.py` | 改造 — 优先从 SQLite 加载 BM25 |
| `rag/pipeline.py` | 索引时调用 bm25_store 持久化 |
| `tests/test_bm25_store.py` | 新建 — 测试 |

---

## 2. SQLite 统一目录

### 问题

当前 3 个 SQLite 文件分散在不同位置：
- `memory.db` — 对话记忆（项目根目录）
- `data/users.db` — 用户系统（data/ 目录）
- `data/analysis.db` — 分析数据（data/ 目录）

### 方案

统一放到 `data/` 目录下：

```
data/
├── memory.db          # 对话记忆
├── users.db           # 用户系统
├── analysis.db        # 分析数据
├── bm25_index.db      # BM25 倒排索引（新增）
├── upload/            # 上传的文档
└── qdrant_data/       # Qdrant 向量数据
```

### 文件变更

| 文件 | 改动 |
|------|------|
| `config.py` | 更新默认路径为 `data/xxx.db` |
| `rag/memory.py` | 默认 db_path 改为 `data/memory.db` |
| `rag/tracker.py` | 默认 db_path 改为 `data/memory.db` |
| `rag/pipeline.py` | 传递新路径 |
| `start.py` | 确保 `data/` 目录存在 |

---

## 3. JWT Secret 持久化

### 问题

JWT secret 未设置时每次重启随机生成，导致：
- 重启后所有用户 token 失效
- 多实例部署时 token 不互通

### 方案

首次启动生成 secret，写入 `data/jwt_secret.txt`，后续读取。

### 实现

```python
# rag/auth.py
_JWT_SECRET_FILE = Path(__file__).resolve().parent.parent / "data" / "jwt_secret.txt"

def _load_or_create_secret() -> str:
    env_secret = os.environ.get("RAG_JWT_SECRET")
    if env_secret:
        return env_secret
    if _JWT_SECRET_FILE.exists():
        return _JWT_SECRET_FILE.read_text().strip()
    # 首次生成
    secret = secrets.token_urlsafe(32)
    _JWT_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _JWT_SECRET_FILE.write_text(secret)
    return secret

_JWT_SECRET = _load_or_create_secret()
```

### 文件变更

| 文件 | 改动 |
|------|------|
| `rag/auth.py` | 改用 `_load_or_create_secret()` |
| `data/jwt_secret.txt` | 自动生成（加入 .gitignore） |
| `.gitignore` | 添加 `data/jwt_secret.txt` |

---

## 4. 前端组件化（后续做）

### 问题

`static/index.html` 1690 行单文件，难维护。

### 方案

拆分为多个文件：

```
static/
├── index.html          # HTML 结构（~200 行）
├── css/
│   └── style.css       # 样式（~400 行）
├── js/
│   ├── api.js          # API 调用封装（~100 行）
│   ├── auth.js         # 登录/注册逻辑（~100 行）
│   ├── chat.js         # 聊天逻辑（~200 行）
│   ├── files.js        # 文件管理（~100 行）
│   └── sidebar.js      # 侧边栏逻辑（~100 行）
└── favicon.ico         # 图标
```

**注意：** 这个后续做，先把后端技术债修完。

---

## 实现顺序

| 阶段 | 内容 | 依赖 |
|------|------|------|
| 1 | SQLite 统一目录 | 无 |
| 2 | JWT Secret 持久化 | 无 |
| 3 | BM25 持久化 | 阶段 1（需要 bm25_index.db 路径） |
| 4 | 前端组件化 | 后续做 |

---

## 验收标准

1. `data/` 目录下有 4 个 SQLite 文件（memory、users、analysis、bm25_index）
2. 重启后 JWT token 不失效
3. BM25 索引持久化到 SQLite，查询时不重建
4. 220+ 测试全过
