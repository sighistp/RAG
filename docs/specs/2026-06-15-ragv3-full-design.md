# RAGv3 完整项目设计文档

> **日期：** 2026-06-15
> **状态：** 已完成 + 迭代中
> **作者：** sighistp
> **技术栈：** Python 3.12 + FastAPI + Qdrant + DeepSeek + 百炼 + SQLite + Vue 3（规划中）

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [技术栈](#3-技术栈)
4. [核心模块](#4-核心模块)
5. [数据模型](#5-数据模型)
6. [API 设计](#6-api-设计)
7. [安全设计](#7-安全设计)
8. [容错设计](#8-容错设计)
9. [并发设计](#9-并发设计)
10. [评估体系](#10-评估体系)
11. [前端设计](#11-前端设计)
12. [部署架构](#12-部署架构)
13. [测试策略](#13-测试策略)
14. [已知问题与遗留](#14-已知问题与遗留)
15. [下一阶段计划](#15-下一阶段计划)

---

## 1. 项目概述

### 1.1 定位

RAGv3 是一个基于检索增强生成（RAG）的智能知识库系统。用户上传文档后，系统自动索引并通过自然语言问答获取知识。支持多用户、多知识库、Agent 工具调用。

### 1.2 核心能力

| 能力 | 说明 |
|------|------|
| 混合检索 | 向量检索 + BM25 + RRF 融合 + 重排序 |
| 多格式支持 | txt, md, pdf, docx, xlsx, csv |
| 多轮对话 | SQLite 持久化 + 自动摘要压缩 |
| Agent 推理 | LangChain ReAct + 4 工具（检索/计算/SQL/图表） |
| 多用户系统 | JWT 认证 + 对话管理 + 反馈 |
| 多知识库 | Qdrant 多 collection 隔离 |
| 安全防护 | 注入检测 + 输入净化 + 输出审查 |
| 容错机制 | 重试 + 熔断 + 缓存 + 降级 |

### 1.3 关键指标

| 指标 | 值 |
|------|-----|
| 测试数量 | 248 个全过 |
| 核心模块 | 24 个 Python 模块 |
| API 端点 | 15+ 个 |
| 支持格式 | 6 种（txt/md/pdf/docx/xlsx/csv） |
| 检索方式 | 向量 + BM25 + RRF 混合 |
| Prompt 版本 | router v3, agent_system v4 |
| 评估 Hit Rate | 90.9%（11 题） |
| 压测 QPS | 1.9（3 并发，0% 错误率） |

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面                              │
│  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │  static/index.html│  │  Vue 3 前端（规划中）            │  │
│  │  暗黑科技风聊天   │  │  Vue 3 + Vite + TypeScript      │  │
│  └────────┬────────┘  └──────────────┬──────────────────┘  │
│           └──────────────┬───────────┘                      │
│                          │ HTTP API                         │
└──────────────────────────┼──────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────┐
│                    FastAPI 后端（单体）                       │
│  ┌───────────────────────┴──────────────────────────────┐  │
│  │  API 层                                               │  │
│  │  /query  /query/stream  /files  /upload  /feedback    │  │
│  │  /conversations  /knowledge-bases  /health            │  │
│  └───────────────────────┬──────────────────────────────┘  │
│  ┌───────────────────────┴──────────────────────────────┐  │
│  │  Pipeline 层                                          │  │
│  │  load → clean → chunk → dedup → embed → store         │  │
│  │  retrieve(vector+BM25+RRF) → rerank → generate        │  │
│  │  → guard(output) → cache → memory → tracker           │  │
│  └───────────────────────┬──────────────────────────────┘  │
│  ┌───────────────────────┴──────────────────────────────┐  │
│  │  Agent 层                                             │  │
│  │  Router(RAG/Agent) → ReAct 循环 → 4 工具              │  │
│  │  retrieve + calculate + sql_query + plot_chart         │  │
│  │  反思机制：工具级重试 + 答案级自检                      │  │
│  └───────────────────────┬──────────────────────────────┘  │
│  ┌───────────────────────┴──────────────────────────────┐  │
│  │  数据层                                               │  │
│  │  Qdrant（向量存储）    SQLite（4 个独立文件）           │  │
│  │  qdrant_data/          data/memory.db                  │  │
│  │                        data/users.db                   │  │
│  │                        data/bm25_index.db              │  │
│  │                        data/analysis.db                │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. 技术栈

### 3.1 后端

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| Web 框架 | FastAPI | 异步、自动 OpenAPI 文档 |
| 向量数据库 | Qdrant（本地模式） | 支持多 collection、payload 过滤 |
| LLM | DeepSeek v4 flash | 通过 OpenAI SDK 调用 |
| Embedding | 百炼 text-embedding-v4 | 1024 维，批量处理 |
| Reranking | 百炼 gte-rerank-v2 | API 调用，5s 超时 |
| Agent 框架 | LangChain | ReAct 推理循环 |
| 认证 | JWT (python-jose) | PBKDF2-HMAC-SHA256 密码哈希 |
| 数据库 | SQLite | 4 个独立文件，WAL 模式 |
| BM25 | rank_bm25 (BM25Okapi) | jieba 中文分词 |

### 3.2 前端

| 组件 | 当前 | 规划 |
|------|------|------|
| 框架 | 原生 HTML/CSS/JS | Vue 3 + Vite + TypeScript |
| UI 库 | 自定义暗黑主题 | Element Plus |
| 状态管理 | 无 | Pinia |
| 路由 | 无（单页面） | Vue Router |

### 3.3 工程工具

| 工具 | 用途 |
|------|------|
| Ruff | Lint + Format（替代 flake8 + isort + black） |
| pytest | 测试框架 |
| pyproject.toml | 项目元数据 + 依赖 + 工具配置 |
| pre-commit | Git hooks（Ruff 自动检查） |
| locust | 性能压测 |

---

## 4. 核心模块

### 4.1 RAG Pipeline（`rag/pipeline.py`）

核心编排器，串联整个检索增强生成流程。

**数据流：**
```
用户问题
  → 安全检查（guard: 注入检测 + 输入净化）
  → 缓存检查（ResultCache: 布隆过滤 + TTL 抖动 + 热点保护）
  → 路由判断（Router: RAG vs Agent）
  → [RAG 路径]
      → 查询改写（LLM 口语→正式）
      → 混合检索（向量 + BM25 + RRF 融合）
      → 重排序（百炼 gte-rerank）
      → 构建消息（系统提示 + 摘要 + 历史 + 上下文）
      → LLM 生成
  → [Agent 路径]
      → LangChain ReAct 循环
      → 工具调用（retrieve/calculate/sql/chart）
      → 反思自检（最多 2 轮）
  → 输出审查（guard: 敏感信息过滤）
  → 记录追踪（tracker: 路由/答案/耗时/工具调用）
  → 保存记忆（memory: 多轮对话 + 自动摘要）
  → 写入缓存
```

**关键设计决策：**
- `file_path` 和 `kb_id` 二选一：file_path 索引新文档，kb_id 查询已有知识库
- `session_id` 管理多轮对话记忆
- `doc_name` 可选过滤检索范围

### 4.2 混合检索（`rag/retriever.py`）

**三路检索 + RRF 融合：**

```
查询 → 向量检索（Qdrant, top_k*2）
     → BM25 检索（BM25Okapi, top_k*2）
     → RRF 融合（k=60）
     → Top-K 结果
```

**BM25 持久化：**
- 首次查询：从 Qdrant scroll 全量 chunks → 构建 BM25Okapi → 存入 SQLite
- 后续查询：从 SQLite 加载 chunks → 构建 BM25Okapi（避免 Qdrant scroll 网络开销）

**中文分词：** jieba（失败时 fallback 到字符 unigram）

### 4.3 Agent（`rag/agent.py`）

**架构：** LangChain Agent + Router + ReAct 推理循环

**工具：**

| 工具 | 功能 | 安全措施 |
|------|------|---------|
| retrieve | 知识库检索 | top_k=10 |
| calculate | 数值计算 | AST 白名单（+ - * / ** %） |
| sql_query | SQL 查询 | 只允许 SELECT，禁止分号注入 |
| plot_chart | 图表生成 | 限制类型（bar/line/pie/scatter） |

**反思机制：**
- **工具级：** 异常/空结果时自动重试一次
- **答案级：** LLM 自检覆盖度，fail 时带缺失要点重跑，最多 2 轮

**路由：** LLM 快速分类，返回 "rag" 或 "agent"

### 4.4 数据清洗（`rag/cleaner.py`）

```
原始文本
  → 编码检测（chardet + 常见编码 fallback）
  → 特殊字符清理（BOM、零宽空格、控制字符）
  → 段落去重（normalized hash + SequenceMatcher 0.95 阈值）
  → 元数据提取（标题/作者/日期，正则）
  → 清洁文本 + 元数据
```

### 4.5 Prompt 管理（`rag/prompt_manager.py`）

**YAML 文件化存储：**
```
prompts/
├── agent_system.yaml   (v4)
├── router.yaml         (v3)
├── rewrite.yaml        (v1)
└── quality_check.yaml  (v1)
```

**API：**
- `get(name, version=None)` — 加载模板（默认最新版本）
- `render(name, **kwargs)` — 加载 + 模板变量替换
- `list_versions(name)` — 列出所有版本

### 4.6 多轮对话记忆（`rag/memory.py`）

**存储：** SQLite `messages` + `sessions` 表

**消息构建：**
```
[system] 系统提示（引用指令 + 术语保留规则）
[system] 对话历史摘要（超过 10 轮时自动生成）
[user/assistant] 最近 10 轮对话
[user] 相关文档上下文（带来源标注）+ 用户问题
```

**自动摘要：** 超过 10 轮时，用 LLM 压缩旧对话为摘要，释放 token 空间。

### 4.7 多用户系统（`rag/user_db.py`）

**数据模型：**
- `users` — 用户表（用户名、密码哈希、salt）
- `conversations` — 对话表（用户 ID、标题、时间）
- `chat_messages` — 消息表（对话 ID、角色、内容）
- `feedback` — 反馈表（消息 ID、用户 ID、值、评论）

**认证流程：**
```
注册 → hash_password(password) → 存入 users 表 → 返回 JWT
登录 → verify_password(password, stored) → 返回 JWT
请求 → decode_token(token) → 获取 user_id
```

### 4.8 多知识库管理（`rag/knowledge_base.py`）

**基于 Qdrant 多 collection：**
- 系统集合：`rag_docs`（默认）
- 用户集合：`kb_{name}_{hex}` 前缀

**安全防护：**
- `list_kbs()` 只返回 `kb_` 前缀的集合
- `delete_kb()` 拒绝删除非 `kb_` 前缀的集合

---

## 5. 数据模型

### 5.1 SQLite 数据库布局

```
data/memory.db
├── messages (id, session_id, role, content, created_at)
├── sessions (session_id, summary, last_summarized_count, created_at, updated_at)
├── execution_logs (id, timestamp, question, route, answer, total_ms, details)

data/users.db
├── users (id, username, password_hash, created_at)
├── conversations (id, user_id, title, created_at)
├── chat_messages (id, conversation_id, role, content, created_at)
├── feedback (id, message_id, user_id, value, comment, created_at)

data/bm25_index.db
├── bm25_chunks (id, collection, text, doc_name, chunk_index)
├── bm25_meta (key, value)

data/analysis.db
└── (分析数据)
```

### 5.2 Qdrant Payload

```python
{
    "text": "chunk 文本内容",
    "doc_name": "文档名称",
    "chunk_index": 0,
    # 规划中：
    "tags": ["技术", "Python", "教程"]
}
```

### 5.3 Chunk 数据类（`rag/models.py`）

```python
@dataclass(frozen=True)
class Chunk:
    text: str
    doc_name: str
    chunk_index: int
```

`frozen=True` 使其可哈希，支持 RRF 融合时作为 dict key 去重。

---

## 6. API 设计

### 6.1 端点清单

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/health` | 健康检查（Qdrant + SQLite） | 无 |
| POST | `/register` | 用户注册 | 无 |
| POST | `/login` | 用户登录 | 无 |
| GET | `/me` | 当前用户信息 | JWT |
| POST | `/query` | 查询知识库 | API Key |
| POST | `/feedback` | 提交反馈 | JWT |
| GET | `/files` | 列出可索引文件 | 无 |
| POST | `/upload` | 上传文件 | JWT |
| DELETE | `/files/{name}` | 删除文件 | JWT |
| POST | `/index` | 索引文档 | API Key |
| POST | `/index-all` | 索引全部文件 | API Key |
| POST | `/conversations` | 新建对话 | JWT |
| GET | `/conversations` | 列出对话 | JWT |
| DELETE | `/conversations/{id}` | 删除对话 | JWT |
| GET | `/conversations/{id}/messages` | 获取消息 | JWT |
| GET | `/knowledge-bases` | 列出知识库 | API Key |
| POST | `/knowledge-bases` | 创建知识库 | API Key |
| DELETE | `/knowledge-bases/{id}` | 删除知识库 | API Key |
| POST | `/knowledge-bases/{id}/documents` | 添加文档 | API Key |
| DELETE | `/knowledge-bases/{id}/documents/{name}` | 删除文档 | API Key |
| POST | `/knowledge-bases/{id}/query` | 查询知识库 | API Key |

### 6.2 认证方式

两种认证并存：
- **API Key**（`X-API-Key` Header）— 用于知识库操作
- **JWT**（`Authorization: Bearer <token>`）— 用于用户操作

`auth_enabled=False`（默认）时跳过 API Key 校验。

### 6.3 请求 ID

所有请求自动注入 `X-Request-ID`（从 header 读取或生成 UUID），用于日志关联。

---

## 7. 安全设计

### 7.1 Prompt Injection 防护（`rag/guard.py`）

**三层检测：**

| 层 | 检测内容 | 处理 |
|----|---------|------|
| 长度 | 输入 > 5000 字符 | 拒绝 |
| 关键词 | 28 个中英文模式（忽略指令、角色扮演、越狱） | 拒绝 |
| 输出 | system prompt、API key、内部路径泄露 | 替换为 [已过滤] |

**已覆盖的注入模式（28 个）：**
- 中文：忽略之前/以上/上面的指令、无视规则、忘记设定、不受限制的 AI
- 英文：ignore previous/above、forget instructions、disregard、override
- 越狱：roleplay、jailbreak、DAN

### 7.2 输入净化

- 截断 5000 字符
- 去除控制字符（保留换行、制表符）

### 7.3 SQL 注入防护（`rag/tools.py`）

- 只允许 SELECT 语句
- 禁止分号（防止多语句注入）
- 列名清洗：`re.sub(r"[^a-zA-Z0-9_一-鿿]", "_", name)`
- 表名清洗：同上

### 7.4 密码安全

- PBKDF2-HMAC-SHA256，260,000 次迭代
- 随机 16 字节 salt
- `hmac.compare_digest` 防时序攻击

### 7.5 JWT 持久化

- 环境变量 `RAG_JWT_SECRET` > 文件 `data/jwt_secret.txt` > 自动生成
- 重启后 token 不失效

---

## 8. 容错设计（`rag/resilience.py`）

### 8.1 重试机制

```python
@retry(max_attempts=3, backoff_base=1.0, retryable_exceptions=(...))
```

- 指数退避：1s → 2s → 4s
- 随机抖动：+0~0.5s 防惊群
- 应用于：generator、embedder、reranker

### 8.2 熔断器（CircuitBreaker）

```
CLOSED → 连续 5 次失败 → OPEN
OPEN → 30 秒后 → HALF_OPEN（放 1 个探测请求）
HALF_OPEN → 成功 → CLOSED
HALF_OPEN → 失败 → OPEN
```

- generator：熔断时返回 "系统繁忙，请稍后重试。"
- reranker：熔断时跳过重排序，用原始检索结果

### 8.3 结果缓存（ResultCache）

**三重防护：**

| 防护 | 机制 |
|------|------|
| 防穿透 | 布隆过滤器前置（10000 容量，1% 误判率） |
| 防雪崩 | TTL ±10% 随机偏移 |
| 防热点 | 访问 ≥10 次的 key 过期后返回旧值（serve-stale） |

**配置：** TTL 300 秒，最大 1000 条，淘汰最旧条目。

**已知遗留：** `get_stale_keys()` 热点刷新机制未集成到 pipeline（安全但不符合设计文档）。

### 8.4 降级策略

| 组件 | 降级方案 |
|------|---------|
| reranker | 跳过重排序，用原始向量检索结果 |
| generator | 返回 "系统繁忙，请稍后重试。" |
| query_rewriter | 跳过改写，用原始问题检索 |
| embedding | 用 LRU 缓存的最近结果 |

---

## 9. 并发设计

### 9.1 读写锁（`rag/concurrency.py`）

```python
class ReadWriteLock:
    # 多个读可并发，写独占
    def read(self):  # context manager
    def write(self):  # context manager
```

**使用场景：**
- `vector_store.py` — add/clear 用 write()，search 用 read()
- `api.py` — 查询用 read()，索引用 write()

### 9.2 线程安全

| 组件 | 保护方式 |
|------|---------|
| Qdrant 客户端 | ReadWriteLock |
| SQLite 连接 | `check_same_thread=False` + `threading.Lock` |
| Embedder/Generator 客户端 | `threading.Lock` 双重检查锁 |
| ResultCache | `threading.Lock` |
| BM25Store | `threading.Lock` |

### 9.3 异步处理

- `/query` 端点：`async def` + `asyncio.to_thread(pipeline.query, ...)`
- `/index-all` 端点：`async def` + `asyncio.to_thread(index_folder, ...)`
- ContextVar 并发隔离：`contextvars.copy_context().run` 防止 request_id 串号

---

## 10. 评估体系（`rag/eval.py`）

### 10.1 指标

| 指标 | 说明 |
|------|------|
| Hit Rate | 答案包含期望关键词的比例 |
| 平均延迟 | 每次查询的平均耗时（ms） |
| P95 延迟 | 95 分位延迟（ms） |

### 10.2 评估数据集

`data/eval_dataset.jsonl` — 11 题，基于 CloudNova 运维手册。

**覆盖场景：**
- 事实问答（"使用什么协议？"）
- 口语化表达（"服务挂了怎么自动摘除？"）
- 专业术语（"mTLS 的三种配置模式？"）
- 跨章节推理（"配置下发的安全性？"）

### 10.3 Bad Case 归档

失败用例自动归档到 `data/bad_cases.jsonl`，支持手动标注失败原因。

### 10.4 性能压测

**工具：** locust

**结果（3 并发，30 秒）：**
- QPS: 1.9
- 平均延迟: 327ms
- P95: 3.2s
- P99: 6.6s
- 错误率: 0%

---

## 11. 前端设计

### 11.1 当前方案（`static/index.html`）

**风格：** 暗黑科技风（深色背景、JetBrains Mono 字体、霓虹 cyan 点缀、扫描线纹理）

**功能：**
- 登录/注册页面
- 对话侧边栏（列表、搜索、重命名、删除）
- 水平滚动文件选择器
- 聊天界面（消息气泡、来源引用、图表内联显示）
- 文件上传（拖拽 + 进度条）
- 反馈按钮（👍👎）

**问题：** 1690 行单文件，难维护。

### 11.2 规划方案（Vue 3 重写）

**技术栈：** Vue 3 + Vite + TypeScript + Element Plus + Pinia

**页面：**
```
/chat/:id     — 聊天界面（主页）
/files        — 文件管理
/knowledge    — 知识库管理
/analytics    — 分析报告
/settings     — 设置
```

**核心组件：**
- `ChatMessage.vue` — 单条消息（支持流式逐字显示）
- `ChatInput.vue` — 输入框 + 文件上传
- `SourceCard.vue` — 来源引用卡片
- `SuggestedQuestions.vue` — 追问建议
- `FeedbackButtons.vue` — 反馈按钮
- `ConversationList.vue` — 对话历史列表
- `KnowledgeBaseList.vue` — 知识库列表

---

## 12. 部署架构

### 12.1 当前方案

本地运行：`python start.py` → uvicorn 端口 8000 + 浏览器自动打开。

### 12.2 规划方案

**单服务 Docker：**
```dockerfile
FROM python:3.12-slim
# Java 17 JRE（PDF 解析）
# pip install 依赖
# COPY 项目代码
EXPOSE 8000
CMD ["uvicorn", "rag.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml：** 单服务，挂载 data/ 和 qdrant_data/ volumes。

**不采用三服务架构（已废弃）。**

---

## 13. 测试策略

### 13.1 测试分布

| 测试文件 | 数量 | 覆盖模块 |
|---------|------|---------|
| test_pipeline.py | 8 | RAG Pipeline |
| test_agent.py | 6 | Agent + Router |
| test_retriever.py | 5 | 混合检索 |
| test_api.py | 10 | API 端点 |
| test_auth_jwt.py | 4 | JWT 认证 |
| test_user_db.py | 11 | 用户数据库 |
| test_conversations.py | 4 | 对话管理 |
| test_feedback.py | 2 | 反馈 |
| test_guard.py | 5 | 安全防护 |
| test_resilience.py | 12 | 容错机制 |
| test_concurrency.py | 3 | 并发 |
| test_memory.py | 5 | 对话记忆 |
| test_cleaner.py | 18 | 数据清洗 |
| test_eval.py | 7 | 评估系统 |
| test_tracker.py | 5 | 执行追踪 |
| test_prompt_manager.py | 8 | Prompt 管理 |
| test_knowledge_base.py | 6 | 多知识库 |
| 其他（15 个文件） | 120+ | loader/chunker/embedder/generator/reranker/tools/... |

**总计：** 248 个测试全过。

### 13.2 TDD 流程

严格遵循 Red-Green-Refactor：
1. 写失败测试
2. 确认失败（原因正确）
3. 写最小实现
4. 确认通过
5. 全量回归

### 13.3 Mock 策略

- 外部 API（DeepSeek、百炼）全部 mock
- Qdrant 在单元测试中 mock，在 e2e 测试中用真实实例
- SQLite 用 `:memory:` 或 `tmp_path`

---

## 14. 已知问题与遗留

| 问题 | 严重度 | 说明 |
|------|--------|------|
| ResultCache 热点刷新未集成 | 低 | `get_stale_keys()` 存在但未被 pipeline 消费，热点 key 持续返回旧值 |
| 评估集只有 11 题 | 中 | 工业级加固设计要求 30+ 题，未完成 |
| 无流式输出 | 中 | 用户等待全部生成完才看到结果 |
| 前端 1690 行单文件 | 中 | 难维护，规划 Vue 3 重写 |
| 无 Docker/CI/CD | 低 | 部署不便 |
| BM25 非倒排索引 | 低 | 当前存完整 chunks，每次查询仍需在内存构建 BM25Okapi |
| `analysis.db` 可能不存在 | 低 | 被引用但未确认是否创建 |
| 多个 SQLite 连接无统一管理 | 低 | 同一文件多个独立连接，WAL checkpoint 可能冲突 |

---

## 15. 下一阶段计划

**时间线：** 6 周，17 个功能，300+ 测试。

| 阶段 | 周次 | 内容 |
|------|------|------|
| 核心体验 | 第 1 周 | 流式输出 + 追问建议 + 重新生成 |
| 数据能力 | 第 2 周 | 反馈驱动优化 + 检索空白分析 + 标签管理 |
| 前端重写 | 第 3-4 周 | Vue 3 重写（聊天 + 文件 + 知识库 + 对话历史 + 导出） |
| 工程收尾 | 第 5 周 | 后端异步化 + Docker + CI/CD |
| 扩展能力 | 第 6 周 | 批量导入 + 数据源集成（可选） |

详见：`docs/specs/2026-06-15-ragv3-next-gen-design.md`
