# RAG 检索增强生成系统 — 实现计划 & 路线图

> **状态：基本开发完成 ✅**（2026-05-30）
>
> 核心功能全部实现，207 个测试全过，系统可独立运行。
> 剩余工作为可选增强（部署、前端美化、性能优化等）。

> **目标：** 在一台个人电脑上搭建贴近企业落地、成本可控的 RAG 系统，支持混合检索
> **作者：** 大三学生，用于提升 AI Agent + 工程化竞争力
> **TDD：** 全模块严格遵循 RED → GREEN → REFACTOR 流程

---

## 技术栈

| 组件 | 选型 | 备注 |
|------|------|------|
| 向量数据库 | Qdrant 本地模式 (`QdrantClient(path=...)`) | API 与生产集群一致 |
| 嵌入模型 | 百炼 text-embedding-v4 (1024d) | 通过 OpenAI SDK 调用 |
| 生成模型 | DeepSeek v4 flash | 通过 OpenAI SDK 调用 |
| 分块 | LangChain `RecursiveCharacterTextSplitter` | chunk_size=500, overlap=80 |
| 混合检索 | 向量 + BM25Okapi + RRF 融合 | jieba 中文分词（含 fallback） |
| API 服务 | FastAPI + Uvicorn | 10MB 文件限制，临时文件清理 |
| GUI | Streamlit | 自动启动，文件上传，聊天记录保存/加载 |
| 多轮记忆 | SQLite + 自动摘要压缩 | 独立 DialogueMemory 模块 |
| 配置 | pydantic-settings | 环境变量驱动，绝对路径 |
| PDF 解析 | OpenDataLoader PDF | 表格→Markdown，需 Java 17 |
| DOCX 解析 | python-docx | 段落 + 表格提取 |

## 项目结构

```
RAG/
├── rag/                       # RAG 核心包
│   ├── __init__.py
│   ├── models.py              # Chunk 数据类（frozen=True，全链路元数据传递）
│   ├── loader.py              # 文档加载 .txt / .md / .pdf / .docx
│   ├── chunker.py             # RecursiveCharacterTextSplitter → list[Chunk]
│   ├── embedder.py            # 百炼 embedding API（惰性初始化，BATCH_SIZE=10）
│   ├── vector_store.py        # Qdrant 本地模式（Chunk payload，惰性初始化）
│   ├── retriever.py           # 混合检索 + BM25 + RRF（Chunk 对象）
│   ├── reranker.py            # 百炼 gte-rerank API（Chunk 透传）
│   ├── memory.py              # 多轮对话记忆（SQLite + 自动摘要 + 来源格式化）
│   ├── generator.py           # DeepSeek v4 flash（惰性初始化，thinking mode 兼容）
│   ├── pipeline.py            # 建库/查询管道（QueryResult 含 sources）
│   ├── query_rewriter.py      # 口语化问题改写（惰性初始化）
│   ├── agent.py               # LangChain Agent + Router + ReAct 循环
│   ├── tools.py               # 四个工具：calculate / sql_query / plot_chart / import_data
│   └── api.py                 # FastAPI 后端
├── rag/gui.py                 # Streamlit 交互界面（文档上传+数据导入+来源展示）
├── tests/                     # 全部模块的 pytest 测试（82 个）
│   ├── test_loader.py         # 文档加载测试（5 个）
│   ├── test_loader_pdf_docx.py # PDF/DOCX 加载测试（12 个）
│   ├── test_chunker.py        # 文本分块测试（6 个）
│   ├── test_embedder.py       # 嵌入模型测试（2 个）
│   ├── test_vector_store.py   # 向量存储测试（5 个）
│   ├── test_retriever.py      # 混合检索测试（4 个）
│   ├── test_reranker.py       # 重排序测试（4 个）
│   ├── test_generator.py      # 生成测试（2 个）
│   ├── test_models.py         # Chunk 数据类测试（3 个）
│   ├── test_memory.py         # 多轮记忆测试（7 个，含来源格式化）
│   ├── test_pipeline.py       # 管道测试（6 个，含 Agent 路由 + sources）
│   ├── test_api.py            # FastAPI 测试（4 个）
│   ├── test_e2e.py            # 端到端集成测试（1 个）
│   ├── test_query_rewriter.py # 查询改写测试（4 个）
│   ├── test_agent.py          # Agent + Router 测试（4 个）
│   ├── test_tools.py          # 工具测试（13 个）
│   └── conftest.py            # 全局 fixture（自动关闭 Qdrant 客户端）
├── aipy-agent/                # AiPy Pro MCP 智能体扩展（DXT 打包）
│   ├── main.py                # MCP Server（3 工具 + 1 Prompt + 随机端口）
│   ├── manifest.json          # DXT 元数据
│   ├── pyproject.toml         # Python 依赖
│   ├── icon.svg               # 扩展图标
│   └── aipy-agent.dxt         # 打包文件（16.7kB）
├── config.py                  # pydantic-settings 配置（绝对路径）
├── .env                       # API keys（不提交到 git）
├── requirements.txt
├── Dockerfile                 # 容器化构建
├── .dockerignore              # Docker 排除规则
├── docker-compose.yml         # 3 服务编排
├── start.sh                   # 容器启动脚本（SERVICE_MODE 路由）
├── start_all.py               # 一键启动脚本（本地开发）
├── qdrant_data/               # Qdrant 数据目录（自动生成）
├── history/                   # 聊天历史记录（JSON）
├── .streamlit/config.toml     # Streamlit 配置
├── scripts/                   # 测试与对比脚本
│   ├── compare_rerank.py      # rerank 前后对比
│   ├── test_rerank_effect.py  # rerank 效果验证
│   └── test_demo.py           # demo 文档问答测试（11 个问题，91% 通过）
└── docs/
    └── demo-文档.md            # CloudNova 微服务平台运维手册（测试文档）
```

---

## 全部任务列表

> **阶段标签说明：**
> - `阶段一：核心 RAG` — 基础检索增强生成系统
> - `阶段二：企业工程化` — 鉴权、多知识库、评估、监控
> - `阶段三：检索质量` — 重排序、查询改写、引用溯源
> - `阶段四：Agent 能力` — Agent 化改造、MCP 打包

---

### Task 1：项目骨架与配置 `阶段一` ✅

- `requirements.txt` — 所有依赖
- `config.py` — pydantic-settings，绝对路径，`RAG_` 环境变量前缀
- `.env` — DeepSeek + 百炼 API Key

---

### Task 2：文档加载 (loader.py) `阶段一` ✅

- 支持 `.txt` / `.md` 格式
- `FileNotFoundError` / `ValueError` 异常处理

---

### Task 3：文本分块 (chunker.py) `阶段一` ✅

- `RecursiveCharacterTextSplitter`，chunk_size=500, overlap=80
- 中英文分隔符兼容

---

### Task 4：嵌入模型 (embedder.py) `阶段一` ✅

- 百炼 text-embedding-v4 API，1024 维
- 惰性初始化：`_client = None` + `_get_client()`
- 支持批量嵌入，`BATCH_SIZE=10` 分批调用（适配百炼限制）
- test-time mock

---

### Task 5：向量存储 (vector_store.py) `阶段一` ✅

- Qdrant 本地模式
- 惰性初始化，UUID 唯一 ID
- `add()` — upsert with PointStruct
- `search()` — `query_points()` API with payload
- `clear()` — 删集合重建

---

### Task 6：混合检索 (retriever.py) `阶段一` ✅

- 向量检索（Qdrant）+ BM25（`rank_bm25` 库）+ RRF 融合
- 中文分词：jieba（优先）→ 单字 unigram fallback
- Python 3.12 兼容（jieba `ImpImporter` 问题已绕过）

---

### Task 7：生成 (generator.py) `阶段一` ✅

- DeepSeek v4 flash API
- 惰性初始化
- System prompt 约束范围，防幻觉
- 接口：`generate(messages: list[dict]) → str`
- 过滤 `reasoning_content` 字段，兼容 DeepSeek thinking mode

---

### Task 8：管道 (pipeline.py) `阶段一` ✅

- `RAGPipeline(file_path, session_id=None, memory_db_path="memory.db")`
- 加载→分块→嵌入→建库→初始化检索器
- `pipeline.query(question, top_k=8)` → `QueryResult(answer, context, sources)`
- 每次建库前调用 `clear()`，防止旧数据干扰
- 集成 memory 模块，query 时自动组装 messages + 存储问答 + 触发摘要
- top_k 默认 8（原 5），提升长文档尾部章节（附录等）的召回率
- Chunk 元数据全链路传递，sources 含 doc_name + chunk_index + text_preview

---

### Task 9：FastAPI (rag/api.py) `阶段一` ✅

- `POST /index` — 上传文件建库（10MB 限制，临时文件清理）
- `POST /query` — 问答
- `GET /health` — 健康检查
- module-level pipeline 变量，test-time 可替换

---

### Task 10：PDF/DOCX 支持 (loader.py) `阶段一` ✅

- `load_pdf()` — 调用 OpenDataLoader PDF 将 PDF 转为 Markdown（含表格），需 Java 17
- `load_docx()` — 调用 python-docx 按文档顺序提取段落 + 表格单元格，不遗漏表格内容
- `load()` 按扩展名自动分发到对应解析器
- TDD 测试：12 个用例，mock 外部 API
- 环境依赖：Java 17（Amazon Corretto）

---

### Task 10.5：Excel 解析 (loader.py) `阶段二` ✅

**企业价值：** 企业大量数据存放在 Excel 中，支持 `.xlsx` 加载让 RAG 系统能覆盖结构化数据文档。

**架构：** `loader.py` 新增 `load_excel()` 函数，用 `openpyxl` 读取所有 sheet，按行转文本。`load()` 分发逻辑加入 `.xlsx` 扩展名。

**核心代码：**

```python
# rag/loader.py — 新增
def load_excel(file_path: str) -> str:
    """读取 .xlsx 文件，所有 sheet 按行转文本。"""
    from openpyxl import load_workbook
    wb = load_workbook(file_path, read_only=True, data_only=True)
    parts = []
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        parts.append(f"=== Sheet: {sheet} ===")
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            parts.append("\t".join(cells))
    wb.close()
    return "\n".join(parts)

# load() 分发逻辑加入:
elif suffix == ".xlsx":
    return load_excel(file_path)
```

**与 `rag/tools.py` import_data 的区别：**
- `loader.py` 的 `load_excel()` → 把 Excel 转文本，走 RAG 检索流程
- `tools.py` 的 `import_data()` → 把 Excel 导入 SQLite，走 Agent SQL 查询流程
- 两者用途不同，不冲突

**实现步骤（TDD）：**

| 步骤 | 内容 | 测试 |
|------|------|------|
| 1 | `tests/test_loader.py` 新增 3 个测试：正常读取、多 sheet、空文件 | RED |
| 2 | `rag/loader.py` 实现 `load_excel()` + `load()` 分发 | GREEN |
| 3 | `rag/gui.py` 上传类型加入 `xlsx` | — |
| 4 | 全量回归 | 82 + 3 = 85 个 |

**面试话术：** "我用 openpyxl 读取 Excel 所有 sheet，按行转文本后走标准 RAG 流程。和 Agent 的 import_data 工具互补——一个做检索，一个做 SQL 分析。"

---

### Task 11：Streamlit GUI (rag/gui.py) `阶段一` ✅

- 自动启动：`python rag/gui.py` → subprocess `streamlit run`
- 支持 .txt / .md / .pdf / .docx 上传
- 聊天界面 + 上下文展开 + 对话保存/加载（`history/` 目录）
- 已索引文件列表展示与删除
- 系统配置查看

---

### Task 12：多轮对话记忆 (rag/memory.py) `阶段一` ✅

- 独立 `DialogueMemory` 模块，SQLite 持久化
- `add_message()` / `build_messages()` / `should_summarize()` / `summarize_old_rounds()`
- `MAX_ROUNDS = 10`，超阈值自动调用 DeepSeek 压缩旧轮为一段摘要
- Prompt 结构：`[System] + [摘要(system role)] + [最近 N 轮] + [检索上下文 + 问题]`

---

### Task 13：Re-ranking 重排序 (rag/reranker.py) `阶段三` ✅

- `Reranker` 类，封装百炼 gte-rerank API
- 检索 Top 16 → Reranker 精排 Top 5 → LLM 生成
- Pipeline 集成：`pipeline.query()` 中 retrieve → rerank → generate 三步走

---

### Task 14：落地 RAG 产品 `阶段一` ✅

- 测试文档：`docs/demo-文档.md` — CloudNova 微服务平台运维手册
- 11 个问题，9 个通过（82%），2 个失败为语义表达差异

---

### Task 15：查询改写 (rag/query_rewriter.py) `阶段三` ✅

- `rewrite_query(question)` 函数，惰性初始化
- Pipeline 集成：检索前调用改写，用改写后的问题做向量检索
- 6/6 口语化问题测试全过

---

### Task 16：HyDE 假设文档嵌入 `阶段三` ⏳

- **目标：** 让 LLM 先生成一段"假答案"，用假答案的向量去检索，语义对齐更好
- **原理：** 用户问"怎么退款" → LLM 生成"退款流程为..." → 用这段文字的向量去检索
- **优势：** 比查询改写更进一步，直接生成答案形态的文本
- **新增模块：** `rag/hyde.py` — `hyde_query(question)` 函数
- **前提：** Task 15 查询改写完成后评估效果，再决定是否需要 HyDE

---

### Task 17：领域同义词词典 `阶段三` ⏳

- **目标：** 维护领域术语映射，解决特定缩写/简称的检索问题
- **示例：** "k8s" → "Kubernetes"、"熔断" → "Circuit Breaker"、"限流" → "Rate Limiting"
- **方案：** 配置文件 + LLM 辅助扩展，或向量相似度自动发现
- **前提：** 根据实际使用场景决定是否需要，通用场景可能不需要

---

### Task 18：引用溯源 `阶段三` ✅

- **核心改造：** 新增 `rag/models.py` Chunk 数据类（frozen=True），全链路 `list[str]` → `list[Chunk]`
- **改造范围：** chunker → vector_store → retriever → reranker → memory → pipeline → agent → GUI（9 个文件）
- **Pipeline 集成：** `QueryResult` 增加 `sources` 字段，含 doc_name + chunk_index + text_preview
- **Prompt 集成：** SYSTEM_PROMPT 增加引用指令，`build_messages()` 格式化 `[N] doc_name(第M段): text`
- **GUI 展示：** 答案下方折叠面板展示来源列表
- **测试：** 82 个测试全过

---

### Task 19：Agent 化改造 `阶段四` ✅

- **架构：** Router 判断问题复杂度 → 简单走 RAG，复杂走 Agent ReAct 循环
- **四个工具：** calculate / sql_query / plot_chart / import_data
- **新增模块：** `rag/tools.py` + `rag/agent.py`
- **测试：** 71 个测试全过

---

### Task 20：包装为 AiPy Pro 智能体 `阶段四` ✅

- **架构：** `aipy-agent/main.py` — MCP Server (Streamable HTTP) + 3 个工具 + 系统提示注入
- **打包：** `aipy-agent/aipy-agent.dxt`（16.7kB, 18个文件）

---

### Task 21：基本鉴权 (rag/auth.py) `阶段二` ✅

**企业价值：** 没有安全的后端不可能上线。API Key 认证是最小可用的鉴权方案。

**架构：** FastAPI 依赖注入（`Depends`）+ API Key 校验中间件。用户通过 `X-API-Key` Header 传入 key，服务端校验后注入 `user_id` 到请求上下文。

**配置：**

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `RAG_AUTH_ENABLED` | 是否启用鉴权 | `false`（开发模式） |
| `RAG_AUTH_KEYS` | API Key 列表（JSON） | `{"admin": "sk-admin-xxx", "user1": "sk-user-xxx"}` |

**核心代码：**

```python
# rag/auth.py
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """校验 API Key，返回 user_id。AUTH_ENABLED=false 时跳过校验。"""
    if not settings.auth_enabled:
        return "anonymous"
    if api_key is None:
        raise HTTPException(status_code=401, detail="Missing API Key")
    keys = json.loads(settings.auth_keys)  # {"admin": "sk-xxx", ...}
    for user_id, key in keys.items():
        if api_key == key:
            return user_id
    raise HTTPException(status_code=403, detail="Invalid API Key")
```

**API 改造：**

```python
# rag/api.py — 每个端点注入 user_id
@app.post("/index")
async def index(
    file: UploadFile = File(...),
    user_id: str = Depends(verify_api_key),
):
    ...

@app.post("/query", response_model=QueryResponse)
def query(
    req: QueryRequest,
    user_id: str = Depends(verify_api_key),
):
    ...
```

**多用户隔离（可选扩展）：**
- 每个 user_id 关联独立的 `memory.db` session
- `session_id = f"{user_id}_{file_name}_{timestamp}"`
- 不同用户的对话历史互不可见

**实现步骤（TDD）：**

| 步骤 | 内容 | 测试 |
|------|------|------|
| 1 | 写 `rag/auth.py` + `tests/test_auth.py` | 6 个测试：enabled=false 跳过、有效 key 通过、无效 key 403、缺少 key 401、多 key 匹配、空 key 列表 |
| 2 | `config.py` 新增 `auth_enabled`、`auth_keys` | — |
| 3 | `rag/api.py` 改造，注入 `Security(verify_api_key)` | 适配现有 test_api.py（mock auth） |
| 4 | 全量回归测试 | 101 个 |

**代码审查修复：**
- `Depends` → `Security`（OpenAPI 安全方案正确生成）
- `json.loads` 加异常处理（配置格式错误返回 500）
- API 全面中文化（标题、端点描述、错误信息）

**面试话术：** "我用 FastAPI 的 Security 依赖注入做 API Key 鉴权，支持配置开关（开发/生产模式切换），通过 JSON 配置支持多用户 key 管理。"

---

### Task 22：多知识库管理 (rag/knowledge_base.py) `阶段二` ✅

**企业价值：** 企业不可能只有一个索引库，不同部门/项目需要隔离的知识库。

**架构：** Qdrant 原生支持多 collection，每个知识库对应一个独立的 collection。新增 `KnowledgeBase` 管理类，封装知识库的 CRUD 操作。

**核心代码：**

```python
# rag/knowledge_base.py
from dataclasses import dataclass
from qdrant_client.models import Distance, VectorParams
import uuid

@dataclass
class KnowledgeBaseInfo:
    kb_id: str           # 知识库 ID（也是 Qdrant collection 名）
    name: str            # 显示名称
    doc_count: int       # 包含文档数
    created_at: str      # 创建时间

class KnowledgeBaseManager:
    """管理多个知识库的 CRUD。"""

    def __init__(self):
        self._client = _get_client()

    def list_kbs(self) -> list[KnowledgeBaseInfo]:
        collections = self._client.get_collections().collections
        return [self._get_info(c.name) for c in collections]

    def create_kb(self, name: str) -> str:
        kb_id = f"kb_{uuid.uuid4().hex[:8]}"
        self._client.create_collection(
            collection_name=kb_id,
            vectors_config=VectorParams(
                size=settings.embed_dimension,
                distance=Distance.COSINE,
            ),
        )
        return kb_id

    def delete_kb(self, kb_id: str) -> None:
        self._client.delete_collection(kb_id)

    def add_document(self, kb_id: str, file_path: str) -> int:
        text = load(file_path)
        doc_name = file_path.split("/")[-1].split("\\")[-1]
        chunks = chunk(text, doc_name=doc_name)
        embeddings = embed([c.text for c in chunks])
        _add_to_collection(kb_id, chunks, embeddings)
        return len(chunks)

    def remove_document(self, kb_id: str, doc_name: str) -> None:
        self._client.delete(
            collection_name=kb_id,
            points_selector=Filter(must=[
                FieldCondition(key="doc_name", match=MatchValue(value=doc_name))
            ]),
        )
```

**vector_store.py 改造：**

当前 `vector_store.py` 使用硬编码的 `COLLECTION_NAME = "rag_docs"`。改造为接受 `collection_name` 参数：

```python
def add_to_collection(collection_name: str, chunks: list[Chunk], embeddings: list[list[float]]):
    ...

def search_collection(collection_name: str, query_embedding: list[float], top_k: int = 5) -> list[Chunk]:
    ...

# 保留原函数作为默认（向后兼容）
def add(chunks, embeddings):
    add_to_collection(COLLECTION_NAME, chunks, embeddings)
```

**Pipeline 改造：**

```python
class RAGPipeline:
    def __init__(self, file_path: str = None, kb_id: str = "rag_docs",
                 session_id: str = None, memory_db_path: str = "memory.db"):
        self.kb_id = kb_id
        if file_path:
            text = load(file_path)
            doc_name = file_path.split("/")[-1].split("\\")[-1]
            self.chunks = chunk(text, doc_name=doc_name)
            embeddings = embed([c.text for c in self.chunks])
            clear(kb_id)
            add_to_collection(kb_id, self.chunks, embeddings)
        # ... rest of init
```

**API 新增端点：**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/knowledge-bases` | 列出所有知识库 |
| POST | `/knowledge-bases` | 创建知识库（参数：name） |
| DELETE | `/knowledge-bases/{kb_id}` | 删除知识库 |
| POST | `/knowledge-bases/{kb_id}/documents` | 向知识库添加文档 |
| DELETE | `/knowledge-bases/{kb_id}/documents/{doc_name}` | 删除文档 |

**GUI 改造：**
- 侧边栏新增知识库选择器（下拉框）
- 创建/删除知识库按钮
- 上传文档时选择目标知识库

**实现步骤（TDD）：**

| 步骤 | 内容 | 测试 |
|------|------|------|
| 1 | `vector_store.py` 新增 `add_to_collection` / `search_collection` / `delete_doc` | 5 个测试 |
| 2 | `rag/knowledge_base.py` KnowledgeBaseManager | 6 个测试：创建、列表、删除、添加文档、删除文档、空知识库查询 |
| 3 | `rag/api.py` 新增 5 个端点 | 5 个测试 |
| 4 | `rag/pipeline.py` 支持 `kb_id` 参数 | 适配现有测试 |
| 5 | `rag/gui.py` 知识库选择器 | 手动测试 |
| 6 | 全量回归 | 82 + 11 = 93 个 |

**面试话术：** "我用 Qdrant 的多 collection 能力做知识库隔离，每个部门/项目一个独立的向量集合。支持增量文档管理（增删改），不需要重建全库。"

---

### Task 24：评估系统 (rag/eval.py) `阶段二` ✅

**企业价值：** 没有评估就没有优化方向。量化指标驱动迭代，而非凭感觉调参数。

**架构：** 独立的评估模块，读取 JSONL 测试集，自动运行 pipeline 并计算三个核心指标。

**测试集格式 (`data/eval_dataset.jsonl`)：**

```jsonl
{"question": "NovaRegistry 使用什么一致性协议？", "expected_keywords": ["Raft"], "kb_id": "rag_docs"}
{"question": "灰度发布分几个阶段？", "expected_keywords": ["4", "四"], "kb_id": "rag_docs"}
{"question": "mTLS 的三种配置模式是什么？", "expected_keywords": ["STRICT", "PERMISSIVE", "DISABLED"], "kb_id": "rag_docs"}
```

**核心指标：**

| 指标 | 公式 | 含义 |
|------|------|------|
| **Hit Rate** | `命中数 / 总问题数` | 答案中包含期望关键词的比例 |
| **MRR** (Mean Reciprocal Rank) | `avg(1/rank)` | 正确文档在检索结果中的排名质量 |
| **Answer Correctness** | LLM 判断答案是否正确 | 更准确但成本更高 |

**核心代码：**

```python
# rag/eval.py
import json
import time
from dataclasses import dataclass

@dataclass
class EvalResult:
    question: str
    expected_keywords: list[str]
    answer: str
    hit: bool
    sources: list[dict]
    latency_ms: float

def load_dataset(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def evaluate(pipeline, dataset: list[dict]) -> list[EvalResult]:
    results = []
    for item in dataset:
        start = time.time()
        result = pipeline.query(item["question"])
        latency = (time.time() - start) * 1000
        keywords = item["expected_keywords"]
        hit = any(kw.lower() in result.answer.lower() for kw in keywords)
        results.append(EvalResult(
            question=item["question"],
            expected_keywords=keywords,
            answer=result.answer,
            hit=hit,
            sources=result.sources,
            latency_ms=latency,
        ))
    return results

def compute_metrics(results: list[EvalResult]) -> dict:
    total = len(results)
    hits = sum(1 for r in results if r.hit)
    avg_latency = sum(r.latency_ms for r in results) / total if total else 0
    return {
        "total": total,
        "hit_rate": hits / total if total else 0,
        "avg_latency_ms": round(avg_latency, 1),
        "pass": sum(1 for r in results if r.hit),
        "fail": sum(1 for r in results if not r.hit),
    }

def print_report(results: list[EvalResult], metrics: dict) -> None:
    print(f"\n{'='*60}")
    print(f"评估报告: {metrics['pass']}/{metrics['total']} 通过 "
          f"(Hit Rate: {metrics['hit_rate']:.1%})")
    print(f"平均延迟: {metrics['avg_latency_ms']:.0f}ms")
    print(f"{'='*60}")
    for i, r in enumerate(results, 1):
        status = "✅" if r.hit else "❌"
        print(f"{status} Q{i}: {r.question}")
        if not r.hit:
            print(f"   期望关键词: {r.expected_keywords}")
            print(f"   实际回答: {r.answer[:100]}...")
    print()
```

**CLI 使用：**

```bash
python -m rag.eval --dataset data/eval_dataset.jsonl

# 输出示例:
# ============================================================
# 评估报告: 10/11 通过 (Hit Rate: 90.9%)
# 平均延迟: 2340ms
# ============================================================
# ✅ Q1: NovaRegistry 使用什么一致性协议？
# ❌ Q7: 如何保证配置下发的安全性？
#    期望关键词: ['mTLS']
```

**参数调优实验追踪：**

```jsonl
{"timestamp": "2026-05-25T10:00:00", "top_k": 8, "chunk_size": 500, "hit_rate": 0.82, "avg_latency": 2100}
{"timestamp": "2026-05-25T11:00:00", "top_k": 12, "chunk_size": 500, "hit_rate": 0.91, "avg_latency": 2400}
```

**实现步骤（TDD）：**

| 步骤 | 内容 | 测试 |
|------|------|------|
| 1 | 创建 `data/eval_dataset.jsonl`（11 题，基于 Task 14 测试） | — |
| 2 | `rag/eval.py` — `load_dataset` / `evaluate` / `compute_metrics` | 6 个测试 |
| 3 | CLI 入口 `python -m rag.eval` | 手动测试 |
| 4 | 评估历史记录 `data/eval_history.jsonl` | — |

**面试话术：** "我建立了自动化评估系统，用 Hit Rate 和延迟两个指标驱动优化。每次改参数后跑一遍评估集，量化对比效果。比如 top_k 从 5 调到 8，Hit Rate 从 82% 提升到 91%。"

---

### Task 25：监控与日志 (rag/monitor.py) `阶段二` ⬚

**企业价值：** 生产环境必备——每次查询记录耗时、token 数、命中文档，成本可追踪。

**架构：** 结构化日志（JSON Lines）+ SQLite 持久化 + Streamlit 仪表盘。

**数据模型：**

```sql
CREATE TABLE IF NOT EXISTS query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    user_id TEXT DEFAULT 'anonymous',
    session_id TEXT,
    question TEXT,
    route TEXT,           -- 'rag' 或 'agent'
    answer TEXT,
    source_count INTEGER, -- 命中文档数
    latency_ms REAL,      -- 总耗时
    rewrite_ms REAL,      -- 查询改写耗时
    retrieve_ms REAL,     -- 检索耗时
    rerank_ms REAL,       -- 重排序耗时
    generate_ms REAL,     -- 生成耗时
    tokens_input INTEGER, -- 输入 token 数
    tokens_output INTEGER,-- 输出 token 数
    error TEXT            -- 错误信息（如有）
)
```

**核心代码：**

```python
# rag/monitor.py
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass

@dataclass
class QueryMetrics:
    route: str
    latency_ms: float
    rewrite_ms: float = 0
    retrieve_ms: float = 0
    rerank_ms: float = 0
    generate_ms: float = 0
    source_count: int = 0
    tokens_input: int = 0
    tokens_output: int = 0

class QueryMonitor:
    def __init__(self, db_path: str = "monitor.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS query_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                user_id TEXT, session_id TEXT,
                question TEXT, route TEXT, answer TEXT,
                source_count INTEGER, latency_ms REAL,
                rewrite_ms REAL, retrieve_ms REAL,
                rerank_ms REAL, generate_ms REAL,
                tokens_input INTEGER, tokens_output INTEGER,
                error TEXT
            )
        """)
        self._conn.commit()

    def log_query(self, user_id: str, session_id: str,
                  question: str, answer: str, metrics: QueryMetrics):
        self._conn.execute(
            "INSERT INTO query_logs "
            "(user_id, session_id, question, route, answer, source_count, "
            "latency_ms, rewrite_ms, retrieve_ms, rerank_ms, generate_ms, "
            "tokens_input, tokens_output) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (user_id, session_id, question, metrics.route, answer,
             metrics.source_count, metrics.latency_ms,
             metrics.rewrite_ms, metrics.retrieve_ms,
             metrics.rerank_ms, metrics.generate_ms,
             metrics.tokens_input, metrics.tokens_output),
        )
        self._conn.commit()

    @contextmanager
    def track_stage(self, stage: str, metrics: QueryMetrics):
        start = time.time()
        yield
        elapsed = (time.time() - start) * 1000
        setattr(metrics, f"{stage}_ms", elapsed)

    def get_stats(self, hours: int = 24) -> dict:
        row = self._conn.execute(
            "SELECT COUNT(*), AVG(latency_ms), AVG(source_count), "
            "SUM(tokens_input), SUM(tokens_output) "
            "FROM query_logs WHERE timestamp > datetime('now', ?)",
            (f"-{hours} hours",),
        ).fetchone()
        return {
            "query_count": row[0] or 0,
            "avg_latency_ms": round(row[1] or 0, 1),
            "avg_sources": round(row[2] or 0, 1),
            "total_tokens_in": row[3] or 0,
            "total_tokens_out": row[4] or 0,
        }
```

**Pipeline 集成：**

```python
# rag/pipeline.py — 在 query() 中记录各阶段耗时
from rag.monitor import QueryMonitor, QueryMetrics

class RAGPipeline:
    def __init__(self, ...):
        ...
        self.monitor = QueryMonitor()

    def query(self, question: str, top_k: int = 8) -> QueryResult:
        metrics = QueryMetrics(route="rag")
        total_start = time.time()

        with self.monitor.track_stage("rewrite", metrics):
            rewritten = rewrite_query(question)

        with self.monitor.track_stage("retrieve", metrics):
            context = self.retriever.retrieve(rewritten, top_k=top_k)

        with self.monitor.track_stage("rerank", metrics):
            context = self.reranker.rerank(rewritten, context)

        with self.monitor.track_stage("generate", metrics):
            messages = self.memory.build_messages(self.session_id, question, context)
            answer = generate(messages)

        metrics.latency_ms = (time.time() - total_start) * 1000
        metrics.source_count = len(context)

        self.monitor.log_query("anonymous", self.session_id, question, answer, metrics)
        return QueryResult(answer=answer, context=context, sources=sources)
```

**Streamlit 仪表盘 (`rag/dashboard.py`)：**

```python
# rag/dashboard.py
import streamlit as st
from rag.monitor import QueryMonitor

st.set_page_config(page_title="RAG 监控仪表盘", page_icon="📊")
st.title("📊 RAG 监控仪表盘")

monitor = QueryMonitor()

stats = monitor.get_stats(hours=24)
col1, col2, col3, col4 = st.columns(4)
col1.metric("24h 查询数", stats["query_count"])
col2.metric("平均延迟", f"{stats['avg_latency_ms']:.0f}ms")
col3.metric("平均命中源", f"{stats['avg_sources']:.1f}")
col4.metric("总 Token 消耗", f"{stats['total_tokens_in'] + stats['total_tokens_out']:,}")

import pandas as pd
df = pd.read_sql("SELECT timestamp, latency_ms, route FROM query_logs ORDER BY id DESC LIMIT 100", monitor._conn)
st.line_chart(df.set_index("timestamp")["latency_ms"])

cost_embed = stats["total_tokens_in"] * 0.7 / 1_000_000
cost_generate = (stats["total_tokens_in"] + stats["total_tokens_out"]) * 1 / 1_000_000
st.metric("预估成本 (24h)", f"¥{cost_embed + cost_generate:.4f}")
```

**实现步骤（TDD）：**

| 步骤 | 内容 | 测试 |
|------|------|------|
| 1 | `rag/monitor.py` — QueryMonitor + QueryMetrics | 6 个测试：建表、记录查询、各阶段耗时、统计、空数据、成本计算 |
| 2 | `rag/pipeline.py` 集成 monitor | 适配 test_pipeline.py |
| 3 | `rag/dashboard.py` — Streamlit 仪表盘 | 手动测试 |
| 4 | `config.py` 新增 `monitor_db_path` | — |

**面试话术：** "我加了结构化监控，每次查询记录各阶段耗时（改写/检索/重排/生成分离统计）、token 消耗、命中源数量。Streamlit 仪表盘实时展示延迟趋势和成本估算，方便定位瓶颈和控制成本。"

---

### Task 26：反馈闭环 `阶段二` ⏳

- "有用/没用" 按钮 → 存入 SQLite → 用于评估系统
- GUI 答案旁新增反馈按钮
- 反馈数据可作为评估系统的权重参考

---

### Task 27：部署就绪 `阶段二` ⏳

- Dockerfile / docker-compose
- 生产级配置（超时、重试、限流）
- CI/CD 流水线

---

### Task 28：执行追踪日志 (rag/tracker.py) `阶段二` ✅

**企业价值：** Agent 自主调用工具时，出了问题不知道发生了什么。执行追踪记录完整调用链，用于排查。

**设计思路：**
- 每次查询记录：路由决策 → 工具调用链（每个工具的输入/输出/耗时）→ 最终答案
- 存 SQLite（同 memory.db，新表 `execution_logs`）
- 管理端 GUI 可查看执行日志

**数据模型：**

```sql
CREATE TABLE execution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    question TEXT NOT NULL,
    route TEXT NOT NULL,           -- 'rag' 或 'agent'
    answer TEXT,
    total_ms REAL,
    details TEXT                   -- JSON: 工具调用链 [{tool, input, output, ms}, ...]
);
```

**核心代码：**

```python
# rag/tracker.py
import json
import time
import sqlite3
from dataclasses import dataclass, field

@dataclass
class ToolCall:
    tool_name: str
    input: str
    output: str
    duration_ms: float

@dataclass
class ExecutionTrace:
    question: str
    route: str
    answer: str = ""
    total_ms: float = 0
    tool_calls: list[ToolCall] = field(default_factory=list)

class ExecutionTracker:
    def __init__(self, db_path: str = "memory.db"):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE IF NOT EXISTS execution_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            question TEXT NOT NULL,
            route TEXT NOT NULL,
            answer TEXT,
            total_ms REAL,
            details TEXT
        )""")
        conn.commit()
        conn.close()

    def save(self, trace: ExecutionTrace):
        conn = sqlite3.connect(self.db_path)
        details = json.dumps([{
            "tool": tc.tool_name, "input": tc.input,
            "output": tc.output, "ms": tc.duration_ms
        } for tc in trace.tool_calls], ensure_ascii=False)
        from datetime import datetime
        conn.execute(
            "INSERT INTO execution_logs (timestamp, question, route, answer, total_ms, details) VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), trace.question, trace.route, trace.answer, trace.total_ms, details)
        )
        conn.commit()
        conn.close()

    def get_recent(self, limit: int = 20) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM execution_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
```

**集成点：**
- `rag/pipeline.py` — Router 决策后记录 route，Agent/Tool 调用前后记录耗时
- `rag/agent.py` — 工具调用时通过回调通知 tracker
- `rag/gui.py` — 侧边栏"执行日志"展开，点击查看调用链

**实现步骤（TDD）：**

| 步骤 | 内容 | 测试 |
|------|------|------|
| 1 | `rag/tracker.py` — ExecutionTracker + ExecutionTrace + ToolCall | 5 个测试：建表、保存、查询、空数据、JSON 序列化 |
| 2 | `rag/pipeline.py` 集成 tracker | 适配 test_pipeline.py |
| 3 | `rag/gui.py` 侧边栏日志展示 | 手动测试 |

**面试话术：** "Agent 自主调工具时，出了问题很难排查。我加了执行追踪，每次查询记录完整调用链——路由决策、工具输入输出、耗时，存 SQLite 可回溯。出问题时看日志就知道 Agent 选了哪个工具、SQL 查了什么。"

---

### Task 29：危险操作确认 (rag/confirm.py) `阶段二` ⬚

**企业价值：** Agent 自主执行 SQL 写入、批量删除等操作时，需要人工确认，避免误操作。

**设计思路：**
- 工具注册时标记 `requires_confirmation=True`
- Agent 调用危险工具前，暂停执行，返回确认请求
- 用户确认后才真正执行
- 非危险工具照常执行，无感

**核心代码：**

```python
# rag/confirm.py
from dataclasses import dataclass

@dataclass
class ConfirmationRequest:
    tool_name: str
    tool_input: str
    reason: str              # 为什么需要确认
    status: str = "pending"  # pending / approved / rejected

# 危险操作定义
DANGEROUS_TOOLS = {
    "sql_query": lambda inp: _is_dangerous_sql(inp),
}

def _is_dangerous_sql(sql: str) -> bool:
    """判断 SQL 是否为危险操作（写入/删除/修改）"""
    dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]
    upper = sql.strip().upper()
    return any(upper.startswith(kw) for kw in dangerous_keywords)

def requires_confirmation(tool_name: str, tool_input: str) -> ConfirmationRequest | None:
    """检查工具调用是否需要人工确认。不需要则返回 None。"""
    checker = DANGEROUS_TOOLS.get(tool_name)
    if checker and checker(tool_input):
        return ConfirmationRequest(
            tool_name=tool_name,
            tool_input=tool_input,
            reason=f"{tool_name} 检测到危险操作，需要确认",
        )
    return None
```

**集成点：**
- `rag/agent.py` — 工具调用前检查 `requires_confirmation()`，危险操作暂停等待确认
- `rag/gui.py` — 危险操作时显示确认按钮（Streamlit `st.warning` + `st.button`）
- `rag/api.py` — API 返回 `{"needs_confirmation": true, "request": {...}}`，前端二次请求确认

**实现步骤（TDD）：**

| 步骤 | 内容 | 测试 |
|------|------|------|
| 1 | `rag/confirm.py` — requires_confirmation + DANGEROUS_TOOLS | 5 个测试：SELECT 不触发、INSERT 触发、DELETE 触发、非 SQL 工具不触发、大小写不敏感 |
| 2 | `rag/agent.py` 集成确认检查 | 适配 test_agent.py |
| 3 | `rag/gui.py` 确认弹窗 | 手动测试 |

**面试话术：** "Agent 自主执行 SQL 写入等操作时有风险。我加了危险操作确认机制——工具注册时标记是否需要确认，Agent 执行前自动检查，危险操作暂停等用户确认后才执行。这样既保留了 Agent 的自主性，又防止了误操作。"

---

### Task 30：并发安全与 Qdrant 服务器模式 `阶段四` ⬚

**问题：** 当前 Qdrant 本地模式（`QdrantClient(path=...)`）不支持多进程并发访问。单进程内多线程也可能出现锁冲突。

**现状：**
- 本地开发阶段，单进程（GUI 或 API），不存在真实并发
- `vector_store.py` 和 `knowledge_base.py` 共享同一个 `_get_client()` 单例
- 如果未来同时运行 GUI + API，或部署为多 worker 服务，会触发 "already been accessed by another client" 错误

**方案选型：**

| 方案 | 原理 | 适用场景 | 复杂度 |
|------|------|---------|--------|
| 线程锁 + 重试 | `threading.Lock()` + 指数退避 | 单进程多线程 | 低 |
| Qdrant Server 模式 | 启动独立 Qdrant 服务，通过 gRPC/HTTP 连接 | 多进程/生产部署 | 中 |
| 连接池 | 共享连接池管理 | 高并发场景 | 高 |

**推荐：** 先用线程锁保护单进程（方案 1），部署时切换到 Qdrant Server 模式（方案 2）。两者可渐进升级。

**实现步骤（TDD）：**

| 步骤 | 内容 | 测试 |
|------|------|------|
| 1 | `vector_store.py` 添加 `threading.Lock()` 保护所有操作 | 测试多线程并发调用不报错 |
| 2 | `_get_client()` 双重检查锁（double-checked locking） | 测试线程安全初始化 |
| 3 | `_with_retry()` 重试逻辑（指数退避，3 次） | 测试瞬时锁错误重试成功 |
| 4 | `config.py` 新增 `qdrant_mode: "local" \| "server"` 配置 | 测试两种模式切换 |
| 5 | Server 模式：`QdrantClient(url=settings.qdrant_url)` | 测试连接远程 Qdrant |

**面试话术：** "Qdrant 本地模式不支持并发，我做了两层防护：单进程内用线程锁 + 重试机制保护；部署时切换到 Qdrant Server 模式，通过配置开关一行代码切换，零改动业务逻辑。"

---

### Task 31：工业级加固 `阶段四` ✅

**状态：** 完成（含代码审查修复）

**新增模块：**
- `rag/resilience.py` — 重试装饰器、熔断器、结果缓存
- `rag/guard.py` — Prompt Injection 防护、输入净化、输出审查
- `rag/concurrency.py` — 读写锁

**集成修改：**
- `rag/generator.py` — 集成重试 + 熔断
- `rag/reranker.py` — 集成重试 + 降级（timeout 5s）
- `rag/embedder.py` — 集成重试
- `rag/vector_store.py` — 集成读写锁
- `rag/pipeline.py` — 集成 guard（注入拦截 + 输出审查）
- `rag/api.py` — 集成健康检查（组件状态）
- `rag/eval.py` — P95 延迟 + Bad Case 归档 + 报告输出
- `rag/query_rewriter.py` — 集成重试
- `data/eval_dataset.jsonl` — 扩充到 31 题

**代码审查修复（9 项）：**
- ReadWriteLock.write() 未持有锁 → yield 移入 with 块
- CircuitBreaker half_open 放行所有请求 → 限制单探测
- check_output() 混合大小写未替换 → re.sub + IGNORECASE
- ResultCache 非线程安全 → 加 threading.Lock
- ResultCache 无大小限制 → max_size=1000 淘汰最旧
- query_rewriter 未集成 retry → 加 @retry
- save_bad_case() 从未调用 → eval main() 中自动归档
- print_report() 缺 P95 → 新增输出行
- reranker 超时 30s → 5s 符合规范

**测试：** 158 个全过

---

## 实施顺序

```
Task 21: 基本鉴权 ──→ Task 22: 多知识库
                            │
Task 24: 评估系统 ←─────────┘
    │
    ▼
Task 25: 监控与日志 → Task 28: 执行追踪 → Task 29: 危险操作确认 → Task 30: 并发安全
```

**建议顺序：**
1. **Task 21 鉴权** — ✅ 已完成
2. **Task 24 评估系统** — ✅ 已完成
3. **Task 22 多知识库** — ✅ 已完成
4. **Task 25 监控** — 1 天，集成到 pipeline
5. **Task 28 执行追踪** — 1 天，Agent 调用链记录
6. **Task 29 危险操作确认** — 0.5 天，工具级别确认机制
7. **Task 30 并发安全** — 0.5 天，线程锁 + Qdrant Server 模式切换

**总工期：** 约 3 天（剩余）

---

## 面试要点

| 功能 | 面试能讲啥 |
|------|-----------|
| 混合检索 | "我理解了单一检索方案的局限，用向量+BM25+RRF 做了互补" |
| 惰性初始化 | "我知道测试时需要 mock 外部服务，所以设计了可替换的 client 层" |
| TDD | "每个模块先写测试再看它红，再写实现，确保测试有意义" |
| Re-ranking | "我用百炼 gte-rerank API 做精排，Recall@5 提升 10-15%" |
| 查询改写 | "我用 LLM 将口语化问题转正式问法，解决用户表达不精确的检索失败" |
| 多轮对话记忆 | "我设计了独立 Memory 模块 + SQLite 持久化 + 自动摘要压缩，企业级 token 优化" |
| MCP 智能体 | "我把 RAG 系统包装为 MCP Server，暴露 3 个工具，符合 DXT 规范可一键安装" |
| Agent 化 | "我用 LangChain Agent 实现 ReAct 推理循环，Router 自动分流简单/复杂问题，4 个工具协作完成数据分析" |
| 引用溯源 | "我用 frozen Chunk 数据类做全链路元数据传递，答案带 [N] 引用标注，用户可追溯到原文段落" |
| 鉴权 | "我用 FastAPI Security 做 API Key 鉴权，支持配置开关和多用户隔离" |
| 多知识库 | "我用 Qdrant 多 collection 做知识库隔离，支持增量文档管理，不同部门数据互不可见" |
| 执行追踪 | "Agent 自主调工具时，出了问题很难排查。我加了执行追踪，记录完整调用链——路由决策、工具输入输出、耗时，存 SQLite 可回溯" |
| 危险操作确认 | "Agent 自主执行 SQL 写入等操作时有风险。我加了危险操作确认机制，工具标记是否需要确认，执行前自动检查，危险操作暂停等用户确认" |
| 评估系统 | "我用 Hit Rate 和延迟两个指标驱动优化，每次改参数跑评估集量化对比" |
| 监控日志 | "我记录各阶段耗时和 token 消耗，Streamlit 仪表盘实时展示延迟趋势和成本" |
| 并发安全 | "Qdrant 本地模式不支持并发，我用线程锁+重试保护单进程；部署时配置切换到 Server 模式，零改动业务逻辑" |
| Docker 部署 | "我写 Dockerfile 保持开发/生产环境一致" |
| 启动优化 | "我发现 matplotlib 通过 import 链条拖慢所有入口（5.77s），用延迟导入将启动时间降到 0.39s，提速 15 倍" |
| 文件夹索引 | "我把文件管理从 GUI 上传改为文件夹扫描，启动时自动全量索引 data/upload/，精简为两服务架构" |

---

## 待补任务（面试要点审查后新增）

### Task 32: 缓存加固（穿透/雪崩/热点） `阶段五` ✅
- 布隆过滤器防穿透（BloomFilter，bytearray 实现，无外部依赖）
- TTL 随机偏移防雪崩（±10% jitter）
- 热点 key 永不过期 + 异步刷新（hot_threshold + get_stale_keys()）
- 集成到 pipeline.py（query 方法缓存命中）

### Task 33: Agent 反思机制 `阶段五` ✅
- 工具级反思：_wrap_tool_with_reflection() 异常/空结果自动重试一次
- 答案级自检：_check_answer_quality() LLM 自检 + 反馈重跑
- 最大 2 轮反思（总共 3 次推理机会）

### Task 34: 数据清洗管道 `阶段五` ✅
- 编码检测：chardet 自动识别 + 常见编码 fallback
- 乱码清理：BOM、零宽空格、不间断空格、控制字符
- 去重：文档级 MD5 + 段落级 SequenceMatcher（阈值 0.95）
- 元数据提取：正则抽取标题/作者/日期
- 集成到 loader.py 和 pipeline.py

### Task 35: Prompt 版本管理 `阶段五` ✅
- YAML 文件化存储（prompts/ 目录，4 个 prompt 文件）
- PromptManager：get/render/list_versions API
- 版本号 + changelog
- 集成到 query_rewriter.py 和 agent.py（移除硬编码 prompt）

### Task 36: 性能压测 `阶段五` ✅
- locust 压测脚本（scripts/locustfile.py）模拟多用户并发查询
- 一键压测脚本（scripts/run_benchmark.py）：启动 server → 索引文档 → locust headless → 输出报告
- 3 并发 / 30s：55 请求，QPS 1.9，平均延迟 327ms
- 修复 SQLite 线程安全问题（tracker.py check_same_thread=False）

### Task 37: 代码审查 & 修复 `阶段五` ✅
- Critical：`_wrap_tool_with_reflection` 死代码 → 接入 RAGAgent.__init__
- Critical：Pipeline 去重丢弃 SequenceMatcher 结果 → 使用 unique_texts 过滤
- Important：质量自检 JSON 解析 → 剥离 markdown 围栏 + 失败返回 "fail"
- Important：PromptManager 子串匹配 → 前缀匹配
- Important：BloomFilter 线程安全 → 添加 threading.Lock
- 196 个测试全过

### Task 38: Docker 部署 `阶段二` ✅
- Dockerfile（Python 3.12-slim + Java + pip 依赖）
- .dockerignore（排除 .git、缓存、运行时数据）
- start.sh（自动索引 + 启动 API）
- docker-compose.yml（API 服务 + 健康检查）
- .env.example（环境变量模板）
- api.py：/query 返回 sources 字段
- 200 个测试全过

### Task 39: 启动性能优化 `阶段二` ✅

**问题：** API 启动耗时 5.77 秒，根因是模块级 import 链条（`api.py → pipeline.py → agent.py → tools.py → matplotlib`）。

**优化：** 6 个文件的重型 import 改为函数内延迟导入。

| 文件 | 修改 |
|------|------|
| `rag/tools.py` | matplotlib、openpyxl 移入 `plot_chart()` / `import_data()` |
| `rag/agent.py` | `from rag.tools` 移入 `create_agent_tools()` / `_parse_and_plot()` |
| `rag/pipeline.py` | `from rag.agent` 移入 `__init__()` / `query()` |
| `rag/api.py` | `from rag.pipeline` 移入 `/index` 处理函数 |
| `rag/knowledge_base.py` | loader/chunker/embedder/vector_store 移入各方法内部 |

**效果：** api.py 导入 5.77s → 0.39s（提速 15 倍）
**测试：** 200 个全过

### Task 40: 简化启动 + 文件夹自动索引 `阶段二` ✅

**目标：** 精简为两服务（API + 用户端），文件通过 `data/upload/` 文件夹管理，启动时自动全量索引。

**新增文件：**
- `rag/folder_indexer.py` — `scan_folder()` + `index_folder()`（延迟加载重型依赖）
- `data/upload/.gitkeep` — 数据文件夹
- `tests/test_folder_indexer.py` — 7 个测试

**修改文件：**
- `start_all.py` — 重写，集成文件夹扫描，只启动 API + 用户端
  - `folder_indexer` 延迟 import（避免阻塞 5.64s）
  - Streamlit 启动时设置 `_RAG_STREAMLIT=1` 跳过 auto-launch（解决页面永远 "奔跑..." 问题）

**启动问题排查：**
- folder_indexer 模块级 import `chunker`(3.81s) + `embedder`(0.56s) 阻塞 → 改为函数内延迟加载

**效果：** 文件管理从 GUI 上传改为文件夹放置
**测试：** 207 个全过（原 200 + 新 7）

### Task 41: Web UI 美化 `阶段二` ✅

**目标：** 注入自定义 CSS 使界面专业美观。

**美化改动（static/index.html）：**
- Google Fonts（Noto Sans SC + Inter）
- 深色科幻主题
- 聊天气泡圆角（`border-radius: 12px`）
- 标题区域自定义标题 + 副标题
- 已有 API 运行时跳过启动

**启动方式：**
```
python start.py   → API(8000) + Web UI
```

**测试：** 207 个全过

### Task 42: 目录结构规范化 `阶段二` ✅

**目标：** 整理 RAG/RAGv2/RAGv3 三个目录结构，使布局规范统一。

**RAG 改动：**
- `start_all.py`、`run_eval.py`、`start.sh` → `scripts/`
- `data/eval_dataset.jsonl`、`data/eval_history.jsonl` → `data/eval/`
- `benchmark_results*.csv` → `benchmarks/`
- 删除临时文件（test_excel.xlsx、test_tmp.txt、memory.db）
- 更新 start_all.py 的 `PROJECT_ROOT`（`.parent` → `.parent.parent`）
- 更新 run_eval.py、rag/eval.py、Dockerfile 的路径引用
- 新增 `history/.gitkeep`，更新 `.gitignore`

**RAGv2/RAGv3 改动：**
- 新增 `prompts/`（从 RAG 复制 4 个 YAML 模板）
- 删除空 `docs/`
- 新增 `history/.gitkeep`
- 更新 `.gitignore`

**最终结构：**
```
RAG/（或 RAGv2/RAGv3）
├── config.py + .env + .gitignore + requirements.txt
├── rag/          # 核心代码包（24+ 模块）
├── prompts/      # Prompt 模板
├── data/upload/  # 数据文件
├── history/      # 聊天历史
├── scripts/      # 启动/评估脚本（仅 RAG）
├── tests/        # 测试（仅 RAG）
└── .streamlit/   # Streamlit 配置
```

**测试：** 207 个全过

---

## 开发完成总结

**完成日期：** 2026-05-30

### 已完成的核心功能

| 阶段 | 功能 | 状态 |
|------|------|------|
| 阶段一 | 文档加载（txt/md/pdf/docx/xlsx） | ✅ |
| 阶段一 | 文本分块 + 向量嵌入 + Qdrant 存储 | ✅ |
| 阶段一 | FastAPI API 服务 | ✅ |
| 阶段一 | Streamlit GUI（管理端 + 用户端） | ✅ |
| 阶段二 | 混合检索（向量 + BM25 + RRF） | ✅ |
| 阶段二 | 多轮对话记忆（SQLite + 自动摘要） | ✅ |
| 阶段三 | Rerank 重排序 | ✅ |
| 阶段三 | 引用溯源（来源展示） | ✅ |
| 阶段四 | Agent 化（工具调用 + 路由） | ✅ |
| 阶段四 | 安全层（注入防护 + 输入净化） | ✅ |
| 阶段四 | 执行追踪 + 结果缓存 | ✅ |
| 阶段五 | Prompt 模板管理 | ✅ |
| 阶段五 | 数据清洗 + 并发限流 + 熔断 | ✅ |
| 阶段五 | 性能压测（Locust） | ✅ |
| 阶段二 | 简化启动 + 文件夹自动索引 | ✅ |
| 阶段二 | GUI 美化 + API 自启动 | ✅ |
| 阶段二 | 目录结构规范化 | ✅ |
| 阶段四 | Agent 路由精准化（区分事实查询 vs 工具任务） | ✅ |
| 阶段四 | Agent 按需画图（不主动生成图表） | ✅ |
| 阶段二 | 统一文件上传（按扩展名自动路由） | ✅ |
| 阶段五 | 代码审查修复（api.py bug、chardet 依赖） | ✅ |

### 技术指标

| 指标 | 值 |
|------|-----|
| 测试数量 | 215 个全过 |
| 核心模块 | 24 个 |
| 支持格式 | txt, md, pdf, docx, xlsx, csv |
| 前端 | Web UI（static/index.html） |
| 启动方式 | `python start.py` |
| 嵌入维度 | 1024d |
| 检索方式 | 向量 + BM25 + RRF 混合 |
| Prompt 版本 | router v3, agent_system v4 |
| Agent 检索量 | top_k=10 |

### 已知问题

| 问题 | 状态 | 说明 |
|------|------|------|
| Agent 图表在 Streamlit GUI 中显示为裂图 | 搁置 | 图片文件正常生成，但 `st.image()` 显示 broken image。待网页版用 `<img>` 标签解决 |
| RAGv2 零测试覆盖 | 待补 | RAG 有 207 个测试，RAGv2 没有 tests/ 目录 |
| folder_indexer 重建后 BM25 索引过时 | 待修 | 重建集合后旧 Retriever 的内存 BM25 索引不更新 |

### 今日修复汇总（2026-05-30）

| 修复项 | 文件 | 状态 |
|--------|------|------|
| api.py /health 端点 bug | `rag/api.py` | ✅ |
| chardet 依赖缺失 | `requirements.txt` | ✅ |
| Router 路由误判 | `prompts/router.yaml` v3 | ✅ |
| Agent 自动画图问题 | `prompts/agent_system.yaml` v4 | ✅ |
| Agent 数据检索不完整 | `rag/agent.py` top_k=10 | ✅ |
| agent.py JSON 空值保护 | `rag/agent.py` | ✅ |
| 图表中文字体缺失 | `rag/tools.py` | ✅ |
| 图表路径自动注入 | `rag/agent.py` | ✅ |

### 第三轮代码审查修复（2026-05-31）

| 级别 | 修复项 | 文件 | 状态 |
|------|--------|------|------|
| Critical | CircuitBreaker 线程安全 | `resilience.py` | ✅ |
| Critical | SQLite 连接线程锁 + close() | `memory.py` + `tracker.py` | ✅ |
| Critical | api.py 全局 pipeline 加锁 | `api.py` | ✅ |
| Critical | requests 依赖缺失 | `requirements.txt` | ✅ |
| Important | SQL 分号注入防护 | `tools.py` | ✅ |
| Important | 表名正则净化 | `tools.py` | ✅ |
| Important | Agent 工具 unwrap try/finally | `pipeline.py` | ✅ |
| Important | sanitize_input 移除 \r | `guard.py` | ✅ |
| Minor | ToolCall Pydantic 属性访问 | `agent.py` | ✅ |

**同步范围：** RAG、RAGv2、RAGv3 三个目录全部同步

### RAGv3 多用户系统（2026-06-01）✅

| 项目 | 说明 |
|------|------|
| 新增文件 | `rag/user_db.py`、4 个测试文件 |
| 新增端点 | `/register`、`/login`、`/me`、`/conversations`、`/upload`、`/feedback` |
| 前端功能 | 登录/注册 + 对话侧边栏 + 文件上传/删除 + 反馈按钮 |
| 安全 | JWT 认证、所有权验证、密码哈希、XSS 防护 |
| 代码审查 | 3C + 5I 修复 |
| 评估修复 | P0: async 端点 + ReadWriteLock；P1: 异常日志；P2: BM25 + logging + 去重 |
| 工程基础设施 | pyproject.toml + logging_config + Ruff lint/format + embedding 缓存 |
| 基础设施审查 | BM25 分页 + ContextVar 并发 + logging 初始化时机 |
| 测试 | 25 个全过 |

### 可选后续

- 部署到云平台（Docker + Qdrant Cloud）
- Agent 工具调用 cl.Step 可视化（需包装 agent tools）
- 流式输出（需改 generator 支持 streaming）
- 评估系统完善（自动 Hit Rate 测试）
- 多语言支持
- RAGv2 补测试覆盖
- 修复 folder_indexer 重建后 BM25 索引过时问题
