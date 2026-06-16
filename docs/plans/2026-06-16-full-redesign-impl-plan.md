# RAGv3 全面重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 前端布局重构 + 知识库系统 + 流式/反馈/追问对接 + 已知 bug 修复

**Architecture:** Vue 3 + Element Plus 前端重构，FastAPI 后端扩展，SQLite 新增 kb_metadata/kb_documents 表

**Tech Stack:** Vue 3, Vite, TypeScript, Element Plus, Pinia, FastAPI, SQLite, Qdrant, DeepSeek

---

## Phase 1：前端布局重构（第 1 天）

### Task 1.1: 侧边栏导航 + 用户右上角

**Files:**
- Modify: `frontend/src/views/MainLayout.vue`

**改动：**
- 顶部导航（对话/文件/知识库/分析）移到侧边栏
- 用户头像从侧边栏底部移到右上角
- 右上角用户下拉菜单（退出登录）
- 删除顶部 topbar-nav

- [ ] **Step 1: 修改 MainLayout 模板**

侧边栏结构：
```
品牌 → 新建对话按钮 → 导航菜单（对话/文件/知识库/分析）→ 分割线 → 暂存文件列表 → 分割线 → 对话列表
```

顶部结构：
```
页面标题（左）→ 用户头像下拉（右）
```

- [ ] **Step 2: 跑测试确认不破坏**

Run: `python -m pytest tests/test_api.py -q --tb=line`

- [ ] **Step 3: 构建前端**

Run: `cd frontend && npm run build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/MainLayout.vue
git commit -m "refactor: move nav to sidebar, user avatar to top-right"
```

---

### Task 1.2: 页面标题修复

**Files:**
- Modify: `frontend/src/views/MainLayout.vue`

**改动：**
- 根据当前路由显示不同标题
- 对话页 → 当前对话标题
- 文件页 → "文件管理"
- 知识库页 → "知识库管理"
- 分析页 → "分析报告"

- [ ] **Step 1: 添加 pageTitle computed**

```typescript
const pageTitle = computed(() => {
  if (route.name === 'files') return '文件管理'
  if (route.name === 'knowledge') return '知识库管理'
  if (route.name === 'analytics') return '分析报告'
  return chatStore.currentConversation?.title || '新对话'
})
```

- [ ] **Step 2: 跑测试 + 构建 + Commit**

---

### Task 1.3: 侧边栏文件选择器

**Files:**
- Modify: `frontend/src/views/MainLayout.vue`
- Modify: `frontend/src/stores/chat.ts`
- Modify: `frontend/src/stores/files.ts`

**改动：**
- 侧边栏底部显示暂存文件列表（第一版显示所有文件，Task 3.4 完成后过滤 in_kb=false）
- 单选模式（后端 doc_name 只支持单文件过滤）
- 选中状态存入 chatStore.selectedFile
- 切换对话时恢复选中状态

- [ ] **Step 1: chat store 新增 selectedFile**

```typescript
const selectedFile = ref<string | null>(null)

function selectFile(name: string | null) {
  selectedFile.value = name
}
```

- [ ] **Step 2: 侧边栏模板添加文件列表（单选）**

```vue
<div class="sidebar-files">
  <div class="section-label">文件过滤</div>
  <div class="file-item" @click="chatStore.selectFile(null)"
       :class="{ active: !chatStore.selectedFile }">
    <span>全部文件</span>
  </div>
  <div v-for="file in filesStore.files" :key="file.name"
       class="file-item" @click="chatStore.selectFile(file.name)"
       :class="{ active: chatStore.selectedFile === file.name }">
    <span class="file-name">{{ file.name }}</span>
  </div>
</div>
```

- [ ] **Step 3: 切换对话时恢复选中文件**

- [ ] **Step 4: 跑测试 + 构建 + Commit**

---

### Task 1.4: 检索范围状态提示

**Files:**
- Modify: `frontend/src/views/ChatView.vue`

**改动：**
- 输入框上方显示当前检索范围（单文件模式）
- 未选择 → "搜索全部文件"
- 已选择 → "搜索：文件A [× 清除]"

- [ ] **Step 1: 添加检索范围显示组件**

```vue
<div v-if="chatStore.selectedFile" class="search-scope">
  🔍 搜索：{{ chatStore.selectedFile }}
  <button @click="chatStore.selectFile(null)">×</button>
</div>
<div v-else class="search-scope">
  🔍 搜索全部文件
</div>
```

- [ ] **Step 2: sendMessage 传递 doc_name**

```typescript
body: JSON.stringify({
  question,
  conversation_id: currentConvId.value,
  doc_name: chatStore.selectedFile || undefined
})
```

- [ ] **Step 3: 跑测试 + 构建 + Commit**

---

## Phase 2：流式 + 反馈 + 追问前端对接（第 2 天）

### Task 2.1: 流式聊天完善

**Files:**
- Modify: `frontend/src/stores/chat.ts`

**改动：**
- SSE 解析器已基本实现（上一轮修复），需要完善：
  - sources 显示
  - 追问建议显示
  - 错误处理

- [ ] **Step 1: 确认 sendMessage 的 SSE 解析逻辑完整**

检查：response.ok 检查、行缓冲、token 追加、sources 解析、suggested 解析

- [ ] **Step 2: 跑测试 + 构建 + Commit**

---

### Task 2.2: 反馈按钮完善

**Files:**
- Modify: `frontend/src/stores/chat.ts`
- Modify: `frontend/src/views/ChatView.vue`

**改动：**
- sendFeedback 已调用 API（上一轮修复）
- 需要：点击后变色、再次点击取消、显示已反馈状态

- [ ] **Step 1: 完善 ChatView 反馈按钮 UI**

```vue
<button
  :class="['action-btn', { active: msg.feedback === 'positive' }]"
  @click="handleFeedback(index, 'positive')"
>
  👍
</button>
<button
  :class="['action-btn', { active: msg.feedback === 'negative' }]"
  @click="handleFeedback(index, 'negative')"
>
  👎
</button>
```

- [ ] **Step 2: 跑测试 + 构建 + Commit**

---

### Task 2.3: 追问建议对接

**Files:**
- Modify: `frontend/src/stores/chat.ts`
- Modify: `frontend/src/views/ChatView.vue`

**改动：**
- 流式完成后调用 `/suggest` 端点
- 显示在消息下方

- [ ] **Step 1: sendMessage 流式完成后调 suggest**

```typescript
// 流式结束后
const suggestRes = await axios.post('/suggest', {
  question, answer
}, { headers: auth.getAuthHeaders() })
if (suggestRes.data.questions?.length) {
  suggestedQuestions.value = suggestRes.data.questions
}
```

- [ ] **Step 2: ChatView 显示追问按钮**

```vue
<div v-if="chatStore.suggestedQuestions.length" class="suggestions">
  <button v-for="q in chatStore.suggestedQuestions" :key="q"
    class="suggest-btn" @click="askSuggested(q)">
    {{ q }}
  </button>
</div>
```

- [ ] **Step 3: 跑测试 + 构建 + Commit**

---

### Task 2.4: 对话标题（前 30 字）

**Files:**
- Modify: `frontend/src/stores/chat.ts`

**改动：**
- createConversation 时设置标题为问题前 30 字
- 不调 LLM

- [ ] **Step 1: 修改 createConversation 调用处**

```typescript
// sendMessage 中
if (!currentConvId.value) {
  const conv = await createConversation()
  conv.title = question.slice(0, 30) + (question.length > 30 ? '...' : '')
}
```

- [ ] **Step 2: 跑测试 + 构建 + Commit**

---

## Phase 3：后端知识库扩展（第 3-4 天）

### Task 3.1: kb_metadata 表 + kb_documents 表

**Files:**
- Modify: `rag/user_db.py`
- Create: `tests/test_kb_metadata.py`

- [ ] **Step 1: 写失败测试**

```python
def test_kb_metadata_table_exists():
    """kb_metadata 表应该存在。"""
    ...

def test_kb_documents_table_exists():
    """kb_documents 表应该存在。"""
    ...

def test_kb_documents_chunk_count():
    """kb_documents 应该记录 chunk_count。"""
    ...
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: user_db.py 新增表创建**

```sql
CREATE TABLE IF NOT EXISTS kb_metadata (
    kb_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    overview TEXT,
    user_id INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS kb_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT,
    toc TEXT,
    summary TEXT,
    chunk_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    added_at TEXT DEFAULT (datetime('now')),
    UNIQUE(kb_id, filename)
);
```

- [ ] **Step 4: 跑测试确认通过 + Commit**

---

### Task 3.2: kb_metadata.py — 目录/概述生成

**Files:**
- Create: `rag/kb_metadata.py`
- Create: `tests/test_kb_metadata_gen.py`

- [ ] **Step 1: 写失败测试**

```python
def test_generate_toc_returns_dict():
    """generate_toc 应该返回目录字典。"""
    ...

def test_generate_toc_handles_invalid_json():
    """LLM 返回非 JSON 时应该返回兜底结构。"""
    ...

def test_generate_summary_returns_string():
    """generate_summary 应该返回概述字符串。"""
    ...

def test_generate_summary_handles_error():
    """LLM 调用失败时应该返回空字符串。"""
    ...
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现 kb_metadata.py**

（见设计文档 3.4 节，含错误处理和 JSON 提取）

- [ ] **Step 4: 跑测试确认通过 + Commit**

---

### Task 3.3: knowledge_base.py 扩展

**Files:**
- Modify: `rag/knowledge_base.py`
- Modify: `tests/test_knowledge_base.py`

**改动：**
- `add_document()` 集成目录/概述生成
- `add_document()` 填充 chunk_count
- 新增 `get_document_detail()` 方法
- 新增 `update_overview()` / `update_toc()` / `update_summary()` 方法

- [ ] **Step 1: 写失败测试**

```python
def test_add_document_generates_toc():
    """添加文档到 KB 时应该自动生成目录。"""
    ...

def test_add_document_generates_summary():
    """添加文档到 KB 时应该自动生成概述。"""
    ...

def test_add_document_records_chunk_count():
    """添加文档后 chunk_count 应该 > 0。"""
    ...

def test_get_document_detail():
    """get_document_detail 应该返回文档详情。"""
    ...
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**

- [ ] **Step 4: 跑测试确认通过 + Commit**

---

### Task 3.4: /files 接口增加 in_kb 字段

**Files:**
- Modify: `rag/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: 写失败测试**

```python
def test_files_endpoint_returns_in_kb_field():
    """/files 应该返回每个文件的 in_kb 状态。"""
    ...
```

- [ ] **Step 2: 实现**

```python
def _check_file_in_kb(filename: str) -> bool:
    """检查文件是否已编入任何知识库。"""
    # 查询 kb_documents 表
    ...
```

- [ ] **Step 3: 跑测试 + Commit**

---

### Task 3.5: 新增知识库详情端点

**Files:**
- Modify: `rag/api.py`
- Modify: `tests/test_api.py`

**新增端点：**
- `GET /knowledge-bases/{id}` — 获取详情
- `PUT /knowledge-bases/{id}/overview` — 更新概述
- `PUT /knowledge-bases/{id}/documents/{name}/toc` — 编辑目录
- `PUT /knowledge-bases/{id}/documents/{name}/summary` — 编辑概述

- [ ] **Step 1: 写失败测试（每个端点 1 个）**

- [ ] **Step 2: 实现端点**

- [ ] **Step 3: 跑全量测试 + Commit**

---

### Task 3.6: 多级分块

**Files:**
- Modify: `rag/chunker.py`
- Modify: `rag/vector_store.py`
- Modify: `rag/retriever.py`
- Create: `tests/test_hierarchical_chunk.py`

**改动：**
- chunker.py 新增 `hierarchical_chunk()` 函数：大 chunk（1500 字）+ 小 chunk（300 字）
- 小 chunk 的 payload 包含 `parent_id` 指向大 chunk
- retriever.py 检索后回溯 parent chunk，用大 chunk 作为上下文

- [ ] **Step 1: 写失败测试**

```python
def test_hierarchical_chunk_returns_parent_and_child():
    """应该返回大 chunk 和小 chunk，小 chunk 有 parent_id。"""
    ...

def test_retriever_returns_parent_context():
    """检索命中子 chunk 时，应该返回父 chunk 的完整上下文。"""
    ...
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现 hierarchical_chunk()**

```python
def hierarchical_chunk(text: str, doc_name: str, parent_size=1500, child_size=300) -> tuple[list[Chunk], list[Chunk]]:
    """返回 (parent_chunks, child_chunks)。"""
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=parent_size, chunk_overlap=200)
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=child_size, chunk_overlap=50)

    parent_chunks = parent_splitter.split_text(text)
    all_children = []
    for i, parent_text in enumerate(parent_chunks):
        parent_id = str(uuid.uuid4())
        children = child_splitter.split_text(parent_text)
        for j, child_text in enumerate(children):
            all_children.append(Chunk(
                text=child_text,
                doc_name=doc_name,
                chunk_index=i * 100 + j,  # 编码 parent 关系
            ))
    # ... 返回结构化的 parent/child chunks
```

- [ ] **Step 4: 改 retriever 支持 parent 回溯**

- [ ] **Step 5: 跑全量测试 + Commit**

---

### Task 3.7: 摘要索引

**Files:**
- Modify: `rag/chunker.py`
- Modify: `rag/retriever.py`
- Modify: `rag/pipeline.py`
- Create: `tests/test_summary_index.py`

**改动：**
- chunker.py 新增 `generate_chunk_summaries()` 函数
- 每个 chunk 生成一句话摘要（50-100 字）
- 摘要向量存入 Qdrant payload 的 `summary_embedding` 字段
- retriever.py 双路检索（原文向量 + 摘要向量）+ RRF 融合

- [ ] **Step 1: 写失败测试**

```python
def test_generate_chunk_summaries():
    """应该为每个 chunk 生成一句话摘要。"""
    ...

def test_retriever_searches_both_text_and_summary():
    """检索应该同时查原文向量和摘要向量。"""
    ...
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现 generate_chunk_summaries()**

```python
def generate_chunk_summaries(chunks: list[Chunk]) -> list[str]:
    """为每个 chunk 生成一句话摘要。"""
    summaries = []
    for c in chunks:
        prompt = f"用一句话概括以下内容的核心要点（50字以内）：\n{c.text[:500]}"
        try:
            summary = generate([{"role": "user", "content": prompt}])
            summaries.append(summary)
        except:
            summaries.append(c.text[:100])  # fallback
    return summaries
```

- [ ] **Step 4: 改 retriever 支持双路检索**

- [ ] **Step 5: 跑全量测试 + Commit**

---

## Phase 4：知识库前端（第 6-7 天）

### Task 4.1: 知识库列表页

**Files:**
- Modify: `frontend/src/views/KnowledgeView.vue`

**改动：**
- 显示知识库卡片列表
- 创建知识库按钮
- 删除知识库（二次确认）

- [ ] **Step 1: 重写 KnowledgeView**

```vue
<template>
  <div class="kb-page">
    <div class="kb-header">
      <h2>知识库管理</h2>
      <el-button type="primary" @click="showCreateDialog">
        + 创建知识库
      </el-button>
    </div>
    <div class="kb-grid">
      <div v-for="kb in knowledgeBases" :key="kb.kb_id" class="kb-card">
        <div class="kb-icon">📚</div>
        <div class="kb-name">{{ kb.name }}</div>
        <div class="kb-count">{{ kb.doc_count }} 个文档</div>
        <div class="kb-actions">
          <el-button @click="enterKB(kb.kb_id)">进入</el-button>
          <el-button type="danger" @click="deleteKB(kb.kb_id)">删除</el-button>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 跑测试 + 构建 + Commit**

---

### Task 4.2: 知识库详情页

**Files:**
- Create: `frontend/src/views/KBDetailView.vue`
- Modify: `frontend/src/router/index.ts`

**改动：**
- 显示知识库概述（可编辑）
- 显示目录（可编辑）
- 显示文档列表（含 chunk_count、状态）
- 添加文件按钮
- 从 KB 移除按钮（灰色）
- 删除文件按钮（红色，二次确认）
- "在此知识库中提问"按钮

- [ ] **Step 1: 创建 KBDetailView.vue**

- [ ] **Step 2: 路由添加 /knowledge/:id**

- [ ] **Step 3: 跑测试 + 构建 + Commit**

---

### Task 4.3: 知识库文件管理

**Files:**
- Modify: `frontend/src/views/KBDetailView.vue`

**改动：**
- 添加文件到 KB（从暂存区选择）
- 从 KB 移除文件
- 删除本地文件（二次确认）

- [ ] **Step 1: 实现文件选择 + 添加**

- [ ] **Step 2: 实现移除 + 删除**

- [ ] **Step 3: 跑测试 + 构建 + Commit**

---

### Task 4.4: 知识库提问按钮

**Files:**
- Modify: `frontend/src/views/KBDetailView.vue`
- Modify: `frontend/src/views/ChatView.vue`

**改动：**
- 点击"在此知识库中提问"→ 跳转对话页 → 自动创建对话 → 锁定 KB 检索范围

- [ ] **Step 1: router query 传递 kb_id**

- [ ] **Step 2: ChatView 读取 kb_id 并设置检索范围**

- [ ] **Step 3: 跑测试 + 构建 + Commit**

---

## Phase 5：细节打磨（第 7 天）

### Task 5.1: 侧边栏折叠

- [ ] 小屏幕侧边栏可折叠（只显示图标）
- [ ] 点击展开/收起

### Task 5.2: 错误处理完善

- [ ] loadKBs/loadAnalytics 失败时显示错误提示
- [ ] 全局 axios 错误拦截器

### Task 5.3: 全量回归

- [ ] 跑后端全量测试：`python -m pytest tests/ -q --tb=line`
- [ ] 构建前端：`cd frontend && npm run build`
- [ ] 手动测试所有页面和功能
- [ ] 更新 dev-log
- [ ] 推送 GitHub

---

## Phase 6（可选）：批量导入 + 数据源集成（第 8 天）

### Task 6.1: 批量导入前端

- [ ] 文件上传页面支持批量导入模式
- [ ] 选择模式（qa_pair / document / table）
- [ ] 调用 `/batch-import` 端点

### Task 6.2: 数据源集成

- [ ] RSS 数据源
- [ ] 数据库连接
- [ ] 定时同步

---

## 测试目标

| 阶段 | 新增测试 | 累计 | 说明 |
|------|---------|------|------|
| Phase 1 | +8 | 312 | 文件选择器 + 检索范围逻辑测试 |
| Phase 2 | +8 | 320 | 流式 + 反馈 + 追问 |
| Phase 3 | +25 | 345 | 知识库后端（metadata、目录、概述、in_kb、多级分块、摘要索引） |
| Phase 4 | +10 | 355 | 知识库前端 |
| Phase 5 | +5 | 360 | 打磨 |
| Phase 6 | +5 | 365 | 可选 |

**目标：360+ 测试全过**

## 时间表

| 阶段 | 内容 | 时间 |
|------|------|------|
| Phase 1 | 前端布局重构 | 第 1 天 |
| Phase 2 | 流式 + 反馈 + 追问对接 | 第 2 天 |
| Phase 3 | 知识库后端扩展（含多级分块 + 摘要索引） | 第 3-6 天 |
| Phase 4 | 知识库前端 | 第 7-8 天 |
| Phase 5 | 细节打磨 | 第 9 天 |
| Phase 6 | 批量导入 + 数据源（可选） | 第 9+ 天 |

**总计：约 8-9 天**
