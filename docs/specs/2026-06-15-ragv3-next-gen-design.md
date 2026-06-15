# RAGv3 下一代功能增强设计

> **日期：** 2026-06-15
> **状态：** 待审批
> **目标：** 面试展示 + 实际使用 + 简历加分，全面发展
> **时间线：** 6 周
> **前端：** Vue 3 + Vite + TypeScript + Element Plus
> **后端：** FastAPI 单体 + 全异步化

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    Vue 3 前端                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │ 聊天界面  │ │ 文件管理  │ │ 知识库    │ │ 设置   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘  │
│       └────────────┼───────────┼────────────┘       │
│                    │  HTTP API  │                     │
└────────────────────┼───────────┼─────────────────────┘
                     │           │
┌────────────────────┼───────────┼─────────────────────┐
│              FastAPI 后端（单体）                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  API 层（全异步）                              │   │
│  │  /query (SSE 流式)  /files  /conversations    │   │
│  │  /feedback  /sources  /export  /batch-import  │   │
│  └──────────────────────┬───────────────────────┘   │
│  ┌──────────────────────┴───────────────────────┐   │
│  │  Pipeline 层                                   │   │
│  │  load → clean → chunk → embed → store          │   │
│  │  retrieve → rerank → generate (stream)         │   │
│  └──────────────────────┬───────────────────────┘   │
│  ┌──────────────────────┴───────────────────────┐   │
│  │  数据层                                        │   │
│  │  Qdrant(向量) SQLite(统一数据库)                │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 2. SQLite 布局

**现状：** 4 个独立 SQLite 文件，都在 `data/` 下（已完成迁移）
- `data/memory.db` — 对话记忆 + 执行日志
- `data/users.db` — 用户/对话/消息/反馈
- `data/bm25_index.db` — BM25 索引
- `data/analysis.db` — 分析数据

**方案：** 保持 4 个独立文件不变（有意为之，职责分离）。新增的表按职责分配到对应数据库。

```
data/memory.db
├── messages (对话记忆)
├── sessions (会话)
├── execution_logs (执行追踪)
├── chunk_feedback (chunk 权重)     ← 新增
└── retrieval_gaps (检索空白)       ← 新增

data/users.db
├── users (用户)
├── conversations (对话)
├── chat_messages (聊天消息)
├── feedback (反馈)
└── data_sources (数据源)           ← 新增

data/bm25_index.db
├── bm25_chunks (BM25 索引)
└── bm25_meta (BM25 元数据)

data/analysis.db
└── (分析数据)
```

---

## 3. 功能清单（17 项）

### 第一阶段：核心体验（第 1 周）

| # | 功能 | 说明 |
|---|------|------|
| 1 | 流式输出 | SSE 打字机效果 |
| 2 | 追问建议 | 每次回答后生成 2-3 个推荐问题 |
| 3 | 重新生成 | 点击重新生成，不重复输入 |

### 第二阶段：数据能力（第 2 周）

| # | 功能 | 说明 |
|---|------|------|
| 4 | 反馈驱动检索优化 | chunk 级别权重调整 |
| 5 | 检索空白分析 | 记录未解答查询，生成缺口报告 |
| 6 | 文档标签/分类 | 按标签过滤检索范围 |

### 第三阶段：前端重写（第 3-4 周）

| # | 功能 | 说明 |
|---|------|------|
| 7 | Vue 3 前端框架搭建 | 路由、状态管理、组件库 |
| 8 | 流式聊天界面 | 打字机效果 + 来源引用 + 反馈按钮 |
| 9 | 对话历史 UI | 侧边栏列表、搜索、重命名、删除 |
| 10 | 知识库管理 UI | 多 KB 切换、文档列表、标签管理 |
| 11 | 文件管理 UI | 拖拽上传、进度条、批量操作 |
| 12 | 回答复制 + 对话导出 | 一键复制、导出 Markdown/PDF |

### 第四阶段：工程收尾（第 5 周）

| # | 功能 | 说明 |
|---|------|------|
| 13 | 后端全异步化 | AsyncOpenAI + httpx + AsyncQdrantClient |
| 14 | Docker | Dockerfile + docker-compose |
| 15 | GitHub Actions CI | 自动 lint + test |

### 第五阶段：扩展能力（第 6 周，可选）

| # | 功能 | 说明 |
|---|------|------|
| 16 | 批量导入 | Excel/CSV 结构化数据导入 |
| 17 | API/数据源集成 | RSS/数据库/API 自动同步 |

---

## 4. 核心模块设计

### 4.1 流式输出

**现状：** `generate()` 返回完整字符串，用户等待全部生成完。

**方案：** SSE (Server-Sent Events)

```
前端 fetch(/query/stream) → 后端 async generator → yield SSE events
```

**API 设计：**
```
GET /query/stream?question=xxx&session_id=xxx&doc_name=xxx
Content-Type: text/event-stream

data: {"type": "token", "content": "根据"}
data: {"type": "token", "content": "文档"}
data: {"type": "sources", "sources": [...]}
data: {"type": "suggested", "questions": ["追问1", "追问2", "追问3"]}
data: {"type": "done"}
```

**改动文件：**

| 文件 | 改动 |
|------|------|
| `rag/generator.py` | 新增 `generate_stream(messages)` 返回 `AsyncGenerator[str, None]` |
| `rag/api.py` | 新增 `/query/stream` 端点，`StreamingResponse` |
| `rag/pipeline.py` | 新增 `query_stream()` 方法，流式完成后处理缓存/追踪/记忆 |

**thinking mode 防护体系（必须遵守）：**

`generate_stream()` 是 `generate()` 的流式版本，必须遵守同样的防护规则：
- 处理 `extra_body={"thinking": {"type": "disabled"}}` 关闭 DeepSeek thinking mode
- 过滤 messages 中的 `reasoning_content` 字段
- 走 `CircuitBreaker` 熔断检查
- 走 `@retry` 重试机制
- 调用链：`generate_stream()` → `AsyncOpenAI().chat.completions.create(stream=True)`

**联动设计：**

| 组件 | 流式时行为 | 流式完成后行为 |
|------|-----------|--------------|
| ResultCache | **不走缓存**（SSE 无法缓存中间结果） | 缓存完整结果（供非流式查询使用） |
| Tracker | 不记录 | 记录完整 answer + 耗时 |
| Memory | 不保存 | 保存 user + assistant 消息 |
| Feedback | 不可用 | 启用反馈按钮 |
| 热点 key 刷新 | 不处理 | 不处理（热点刷新与流式无关，后续单独处理） |

**与 ResultCache 的交互规则：**
- 流式查询（`/query/stream`）：**完全绕过 ResultCache**，每次都调 LLM
- 非流式查询（`/query`）：正常走 ResultCache（命中则直接返回）
- 流式完成后将完整结果写入 ResultCache（供非流式查询命中）
- `get_stale_keys()` 热点刷新机制暂不在本次迭代中集成（已知遗留问题，安全但不符合设计文档）

**DeepSeek streaming 支持：**
```python
stream = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=messages,
    stream=True,
)
async for chunk in stream:
    if chunk.choices[0].delta.content:
        yield chunk.choices[0].delta.content
```

### 4.2 追问建议

**方案：** 流式完成后，用 LLM 生成 2-3 个推荐问题

**实现：**
- 在 `/query/stream` 的 SSE 中，`suggested` 事件携带推荐问题
- 用 `generate()` 调用一次 LLM（轻量 prompt）
- 缓存：相同 session + 近似 context 只生成一次

**Prompt：**
```
基于以下问答，生成 3 个用户可能想追问的问题。只输出问题，每行一个。

问题：{question}
回答：{answer}

追问：
```

### 4.3 重新生成

**API：**
```
POST /regenerate
{
  "conversation_id": 123,
  "message_id": 456
}
```

**实现：**
- 找到该 message 对应的原始 query 和 retrieval context
- 用 temperature=0.7 重新生成（比默认 0.3 更随机）
- 保存为新 message，前端替换显示

### 4.4 反馈驱动检索优化

**现状：** feedback 只存数据库，没有用来改进检索。

**方案：** chunk 级别权重调整

**数据模型：**
```sql
CREATE TABLE chunk_feedback (
    chunk_hash TEXT PRIMARY KEY,  -- chunk 内容的 MD5
    weight REAL DEFAULT 1.0,      -- 权重因子
    positive_count INTEGER DEFAULT 0,
    negative_count INTEGER DEFAULT 0,
    last_updated TEXT
);
```

**权重规则：**
- negative 反馈：weight -= 0.1（最低 0.2）
- positive 反馈：weight += 0.1（最高 2.0）
- 每周衰减：weight = 1.0 + (weight - 1.0) * 0.95（趋向 1.0）
- 恶意反馈过滤：同一用户对同一 chunk 只计一次

**改动：**
- `rag/retriever.py` — RRF 融合时乘以 weight 因子
- `rag/feedback_processor.py` — 新建，处理反馈 → 更新权重
- `rag/pipeline.py` — 反馈时触发权重更新

### 4.5 检索空白分析

**判断标准：**
- rerank 后最高分 < 0.3
- 或回答包含"未找到"、"不知道"、"文档中未提及"

**数据模型：**
```sql
CREATE TABLE retrieval_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    best_score REAL,
    timestamp TEXT DEFAULT (datetime('now')),
    resolved BOOLEAN DEFAULT FALSE,
    resolution_note TEXT
);
```

**API 端点：**
```
GET /analytics/gaps         -- 未解答问题列表
GET /analytics/gaps/summary -- 缺口统计（按时间、按频率）
POST /analytics/gaps/{id}/resolve -- 标记已解决
```

**与评估集联动：**
- 检索空白分析发现的高频未解答问题，可一键加入 `data/eval_dataset.jsonl` 评估集
- 评估集从当前 11 题扩充到 30+ 题（工业级加固设计遗留目标）
- 空白分析 → 补充文档 → 重新评估 → 验证修复，形成闭环

**缓存命中率统计（顺带补充）：**
- `ResultCache` 新增命中/未命中计数器
- `/analytics/cache` 端点返回缓存命中率
- 评估报告新增"缓存命中率"指标

### 4.6 文档标签/分类

**方案：** Qdrant payload 中存储标签，检索时可按标签过滤

**API 端点：**
```
POST /files/{name}/tags     -- 给文件打标签
DELETE /files/{name}/tags/{tag} -- 删除标签
GET /tags                   -- 列出所有标签
POST /query (body: {tags: ["技术"]}) -- 按标签过滤检索
```

**Qdrant payload 扩展：**
```python
{
    "text": "...",
    "doc_name": "...",
    "chunk_index": 0,
    "tags": ["技术", "Python", "教程"]  # 新增
}
```

---

## 5. 后端全异步化

### 需要改的同步阻塞点

| 文件 | 当前 | 改为 | 说明 |
|------|------|------|------|
| `rag/embedder.py` | `OpenAI()` | `AsyncOpenAI()` | embedding API 调用 |
| `rag/generator.py` | `OpenAI()` | `AsyncOpenAI()` | 生成 API 调用 |
| `rag/reranker.py` | `requests.Session()` | `httpx.AsyncClient()` | rerank API 调用 |
| `rag/vector_store.py` | `QdrantClient()` | `AsyncQdrantClient()` | 向量数据库操作 |
| `rag/retriever.py` | BM25 同步计算 | `asyncio.to_thread()` | CPU 密集，保持同步 |

### ReadWriteLock 去留

**保留。** Qdrant 本地模式不支持并发写，ReadWriteLock 用于保护写操作。异步化后的分工：

| 操作 | 客户端 | 锁 | 说明 |
|------|--------|-----|------|
| 查询（search/search_collection） | `AsyncQdrantClient` | 不需要锁 | 异步读，Qdrant 支持并发读 |
| 写入（add/clear/add_to_collection/delete_doc） | `QdrantClient`（同步） | `ReadWriteLock.write()` | 在 `asyncio.to_thread()` 中执行，保护写互斥 |
| BM25 加载（scroll） | `QdrantClient`（同步） | `ReadWriteLock.read()` | 在 `asyncio.to_thread()` 中执行 |

### API 端点改造

所有端点改为 `async def`，IO 密集操作用 `await`，CPU 密集操作用 `asyncio.to_thread()`。

### Docker 架构

**单服务模式：** API + 静态文件 serve，不搞多服务。

```
Dockerfile
├── Python 3.12-slim + Java 17 JRE
├── pip install 依赖
├── COPY 项目代码
├── EXPOSE 8000
└── CMD uvicorn rag.api:app --host 0.0.0.0 --port 8000

docker-compose.yml
├── rag-api: build . + ports 8000:8000 + volumes(data, qdrant_data) + env_file
└── (单服务，前端由 FastAPI 静态文件 serve)
```

不采用之前的三服务架构（已废弃）。前端 Vue 3 构建后的静态文件由 FastAPI 直接 serve。

---

## 6. 前端重写设计

### 技术栈

- **Vue 3** + **Vite** + **TypeScript**
- **Element Plus** — UI 组件库
- **Pinia** — 状态管理
- **Vue Router** — 路由

### 页面结构

```
/ (需要登录)
├── /chat/:id        -- 聊天界面（主页）
├── /files           -- 文件管理
├── /knowledge       -- 知识库管理
├── /analytics       -- 分析报告
└── /settings        -- 设置
```

### 核心组件

```
components/
├── ChatMessage.vue       -- 单条消息（支持流式逐字显示）
├── ChatInput.vue         -- 输入框 + 文件上传
├── SourceCard.vue         -- 来源引用卡片
├── SuggestedQuestions.vue -- 追问建议（3 个按钮）
├── FeedbackButtons.vue   -- 反馈按钮（👍👎）
├── FileUploader.vue      -- 文件上传（拖拽 + 进度条）
├── ConversationList.vue  -- 对话历史列表
├── KnowledgeBaseList.vue -- 知识库列表
├── TagManager.vue        -- 标签管理
└── ExportButton.vue      -- 导出按钮（Markdown/PDF）
```

### 流式聊天实现

```typescript
// 前端 SSE 接收
const response = await fetch(`/api/query/stream?question=${question}`)
const reader = response.body.getReader()
const decoder = new TextDecoder()

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  const text = decoder.decode(value)
  // 解析 SSE data: 行
  for (const line of text.split('\n')) {
    if (line.startsWith('data: ')) {
      const event = JSON.parse(line.slice(6))
      if (event.type === 'token') {
        answer.value += event.content  // 逐字追加
      } else if (event.type === 'sources') {
        sources.value = event.sources
      } else if (event.type === 'suggested') {
        questions.value = event.questions
      }
    }
  }
}
```

### 前端重写分期

**第 3 周（基础框架）：**
- Vue 3 项目搭建（Vite + TypeScript + Element Plus）
- 路由 + 状态管理
- 登录/注册页面
- 聊天界面（非流式，先接通 API）
- 文件管理页面

**第 4 周（高级功能）：**
- 流式聊天（SSE 打字机效果）
- 对话历史侧边栏
- 知识库管理页面
- 标签管理
- 反馈按钮 + 追问建议
- 回答复制 + 对话导出

---

## 7. 批量导入（第五阶段）

**API：**
```
POST /batch-import
Content-Type: multipart/form-data
file: xxx.xlsx
mode: qa_pair | document | table
config: {"sheet": "Sheet1", "question_col": "问题", "answer_col": "答案"}
```

**导入模式：**
- `qa_pair` — 每行是一个 QA 对，直接存入知识库
- `document` — 每行是一个文档片段，chunk 后索引
- `table` — 整张表作为结构化数据，支持 SQL 查询（Agent 工具）

---

## 8. 数据源集成（第五阶段，可选）

```
DataSource (抽象基类)
├── RSSSource       -- RSS/Atom 订阅
├── DatabaseSource  -- MySQL/PostgreSQL
└── APISource       -- 通用 REST API
```

**数据模型：**
```sql
CREATE TABLE data_sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,  -- rss/database/api
    config TEXT NOT NULL, -- JSON 配置
    last_sync TEXT,
    sync_interval INTEGER DEFAULT 3600
);
```

**API 端点：**
```
POST /sources              -- 创建数据源
GET /sources               -- 列出数据源
POST /sources/{id}/sync    -- 手动触发同步
DELETE /sources/{id}       -- 删除数据源
```

---

## 9. 面试话术（新增部分）

| 功能 | 面试能讲啥 |
|------|-----------|
| 流式输出 | "SSE 实现打字机效果，AsyncGenerator 逐 token 推送，前端 ReadableStream 实时接收" |
| 反馈驱动优化 | "用户反馈闭环——negative 反馈关联到 chunk 级别，BM25 权重动态调整 0.2~2.0，每周衰减趋向中性" |
| 检索空白分析 | "记录未解答查询，生成知识缺口报告，系统会'告诉'你它不知道什么" |
| 追问建议 | "基于上下文用 LLM 生成 3 个推荐追问，引导用户深入探索" |
| Vue 3 前端 | "Vue 3 + Vite + TypeScript + Element Plus，组件化开发，Pinia 状态管理" |
| 全异步化 | "FastAPI + AsyncOpenAI + httpx + AsyncQdrantClient，全链路异步，零阻塞" |

---

## 10. 简历亮点（可量化）

| 指标 | 当前 | 目标 |
|------|------|------|
| 测试数量 | 248 | 300+ |
| 前端技术栈 | 原生 HTML | Vue 3 + TypeScript |
| API 端点 | 15+ | 25+ |
| 数据源类型 | 本地文件 | 文件 + RSS + 数据库 + API |
| 响应方式 | 同步阻塞 | SSE 流式 |
| 检索质量闭环 | 无 | 反馈驱动 + 空白分析 |

---

## 11. 实现顺序

| 周次 | 内容 | 测试目标 |
|------|------|---------|
| 第 1 周 | 流式输出 + 追问建议 + 重新生成 | +15 |
| 第 2 周 | 反馈驱动优化 + 检索空白分析 + 标签管理 | +15 |
| 第 3 周 | Vue 3 前端基础（框架 + 聊天 + 文件） | +10 |
| 第 4 周 | Vue 3 前端高级（流式 + 对话历史 + 知识库 + 导出） | +10 |
| 第 5 周 | 后端异步化 + Docker + CI/CD | +10 |
| 第 6 周 | 批量导入 + 数据源集成（可选）+ 全量回归 | +5 |

**总计：** 300+ 测试，17 个功能，6 周完成
