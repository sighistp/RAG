# RAGv3 全面重构方案（前端 + 知识库系统）

> **日期：** 2026-06-16
> **状态：** 待实施
> **范围：** 前端布局重构 + 知识库系统 + 流式/反馈/追问前端对接 + 已知 bug 修复

---

## 1. 总体目标

将 RAGv3 从"能用的 demo"升级为"可实际使用的产品"：

- 前端：标准 SaaS 布局，导航在侧边栏，用户右上角，文件/KB 选择器
- 后端：知识库系统扩展（目录/概述自动生成 + 手动编辑）
- 交互：流式聊天、反馈按钮、追问建议全部对接前端
- 安全：修复已知 Critical/Important 问题

---

## 2. 前端重构

### 2.1 布局变更

**当前：**
```
┌──────────────────────────────────────────┐
│  RAG 知识库  [对话] [文件] [知识库] [分析]  │  ← 顶部导航
├──────────┬───────────────────────────────┤
│ 侧边栏    │          内容区               │
│ + 新对话  │                               │
│ 对话列表  │                               │
│ 👤 用户   │                               │  ← 用户在侧边栏底部
└──────────┴───────────────────────────────┘
```

**改为：**
```
┌──────────┬───────────────────────────────┐
│ RAG 知识库 │              [👤 用户名 ▼]    │  ← 用户右上角
│──────────│───────────────────────────────│
│ ＋ 新对话  │          页面标题              │
│          │───────────────────────────────│
│ 💬 对话   │                               │
│ 📄 文件   │          内容区               │
│ 📚 知识库 │                               │
│ 📊 分析   │                               │
│          │                               │
│ ──────── │                               │
│ 暂存文件  │                               │
│ ☐ 文件A  │                               │
│ ☐ 文件B  │                               │
│ ──────── │                               │
│ 对话1 ●  │                               │
│ 对话2    │                               │
└──────────┴───────────────────────────────┘
```

**改动文件：** `frontend/src/views/MainLayout.vue`

### 2.2 页面标题修复

**当前 bug：** 点击文件/知识库/分析页面时，标题仍显示"新对话"。

**修复：**
```typescript
const pageTitle = computed(() => {
  if (route.name === 'files') return '文件管理'
  if (route.name === 'knowledge') return '知识库管理'
  if (route.name === 'analytics') return '分析报告'
  return chatStore.currentConversation?.title || '新对话'
})
```

**改动文件：** `frontend/src/views/MainLayout.vue`

### 2.3 用户头像 + 下拉菜单

**当前：** 用户信息在侧边栏底部，设置按钮是齿轮图标。

**改为：** 右上角用户头像，点击弹出下拉菜单。

```vue
<!-- 右上角 -->
<el-dropdown>
  <div class="user-badge">
    <div class="avatar">{{ userInitial }}</div>
    <span>{{ username }}</span>
  </div>
  <template #dropdown>
    <el-dropdown-menu>
      <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
    </el-dropdown-menu>
  </template>
</el-dropdown>
```

**改动文件：** `frontend/src/views/MainLayout.vue`

### 2.4 侧边栏文件选择器

**功能：** 侧边栏底部显示 `data/upload/` 下的**暂存文件**（未编入任何知识库的文件），带勾选框。已编入知识库的文件在知识库详情页管理，不在侧边栏显示。

**数据流：**
```
侧边栏文件列表 → 用户勾选 → store 记录选中文件
                           → 聊天时传 doc_name 参数
                           → 输入框上方显示当前范围
```

**实现：**
- 侧边栏底部显示暂存文件列表（从 `/files` API 获取）
- 每个文件有勾选框
- 选中状态存入 `chatStore.selectedFiles`
- 切换对话时恢复该对话的选中文件

**改动文件：**
- `frontend/src/views/MainLayout.vue` — 侧边栏文件列表
- `frontend/src/stores/chat.ts` — 新增 `selectedFiles` 状态

### 2.5 检索范围状态提示

**功能：** 输入框上方显示当前检索范围。检索范围绑定到对话，切换对话时自动恢复。

```
未选择文件时：
┌─────────────────────────────────────────┐
│  🔍 搜索全部文件                          │
└─────────────────────────────────────────┘

选择了文件时：
┌─────────────────────────────────────────┐
│  🔍 搜索：文件A、文件B    [× 清除]        │
└─────────────────────────────────────────┘

选择了知识库时：
┌─────────────────────────────────────────┐
│  🔍 在「运维知识库」中搜索  [× 清除]       │
└─────────────────────────────────────────┘
```

**行为规则：**
- **新建对话：** 默认"搜索全部文件"，用户可在侧边栏勾选文件或选择知识库
- **已有对话：** 显示该对话上次使用的检索范围（只读），点击可切换
- **切换对话：** 自动恢复该对话的检索范围
- **知识库详情页点"提问"：** 自动创建新对话，锁定为该知识库

**改动文件：** `frontend/src/views/ChatView.vue`

### 2.6 流式聊天前端对接

**当前：** 后端 `/query/stream` 已实现 SSE，前端需要对接。

**实现：**
```typescript
// frontend/src/stores/chat.ts - sendMessage()
const response = await fetch('/query/stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({ question, conversation_id, doc_name })
})

if (!response.ok) { /* 错误处理 */ }

const reader = response.body!.getReader()
const decoder = new TextDecoder()
let buffer = ''

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buffer += decoder.decode(value, { stream: true })
  const lines = buffer.split('\n')
  buffer = lines.pop() || ''
  for (const line of lines) {
    if (!line.startsWith('data: ')) continue
    const event = JSON.parse(line.slice(6))
    if (event.type === 'token') { /* 逐字追加 */ }
    if (event.type === 'sources') { /* 显示来源 */ }
    if (event.type === 'suggested') { /* 显示追问建议 */ }
  }
}
```

**改动文件：** `frontend/src/stores/chat.ts`

### 2.7 反馈按钮对接

**当前：** 前端 `sendFeedback` 没调后端 API。

**修复：**
```typescript
async function sendFeedback(messageIndex: number, value: 'positive' | 'negative') {
  const msg = messages.value[messageIndex]
  if (!msg) return
  msg.feedback = value
  if (msg.id) {
    await axios.post('/feedback', {
      message_id: msg.id,
      value
    }, { headers: auth.getAuthHeaders() })
  }
}
```

**改动文件：** `frontend/src/stores/chat.ts`

### 2.8 追问建议对接

**当前：** 后端 `/suggest` 已实现，前端未调用。

**实现：** 流式完成后调用 `/suggest`，显示在消息下方。

**改动文件：** `frontend/src/stores/chat.ts`, `frontend/src/views/ChatView.vue`

### 2.9 对话标题

**方案：** 用第一条消息的前 30 个字符作为标题，不调 LLM。

```typescript
// sendMessage() 中
if (!currentConvId.value) {
  const conv = await createConversation()
  conv.title = question.slice(0, 30) + (question.length > 30 ? '...' : '')
}
```

**改动文件：** `frontend/src/stores/chat.ts`

---

## 3. 后端知识库系统扩展

### 3.1 已有端点（前端直接对接）

| 端点 | 方法 | 状态 |
|------|------|------|
| `/knowledge-bases` | GET | ✅ 已有 |
| `/knowledge-bases` | POST | ✅ 已有 |
| `/knowledge-bases/{id}` | DELETE | ✅ 已有 |
| `/knowledge-bases/{id}/documents` | POST | ✅ 已有 |
| `/knowledge-bases/{id}/documents/{name}` | DELETE | ✅ 已有 |
| `/knowledge-bases/{id}/query` | POST | ✅ 已有 |

### 3.2 新增端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/knowledge-bases/{id}` | GET | 获取知识库详情（含文档列表、概述、目录） |
| `/knowledge-bases/{id}/overview` | PUT | 更新知识库概述（手动编辑） |
| `/knowledge-bases/{id}/documents/{name}/toc` | PUT | 编辑文件目录 |
| `/knowledge-bases/{id}/documents/{name}/summary` | PUT | 编辑文件概述 |

### 3.2.1 知识库详情页"提问"按钮行为

点击 [在此知识库中提问] 按钮：
1. 跳转到对话页（`/`）
2. 自动创建新对话
3. 检索范围自动锁定为该知识库
4. 输入框上方显示"🔍 在「运维知识库」中搜索"

实现方式：通过 router query 参数传递 `kb_id`，ChatView 在 `onMounted` 时读取并设置检索范围。

### 3.2.2 文档操作按钮区分

知识库详情页的文档列表每行有两个操作按钮：

| 操作 | 按钮样式 | 行为 | 确认 |
|------|---------|------|------|
| 从知识库移除 | 灰色按钮 | 只移除索引，文件保留在 data/upload/ | 无需确认 |
| 删除文件 | 红色按钮 | 从磁册删除文件 | 二次确认弹窗 |

### 3.3 数据模型扩展

**SQLite (data/users.db) 新增表：**

```sql
-- 知识库扩展信息
CREATE TABLE kb_metadata (
    kb_id TEXT PRIMARY KEY,          -- 对应 Qdrant collection name
    name TEXT NOT NULL,
    description TEXT,
    overview TEXT,                   -- LLM 生成的内容概述
    user_id INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 知识库内文档详情
CREATE TABLE kb_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT,
    toc TEXT,                        -- LLM 生成的目录（JSON）
    summary TEXT,                    -- LLM 生成的文档概述
    chunk_count INTEGER DEFAULT 0,   -- 该文档的 chunk 数量
    status TEXT DEFAULT 'pending',   -- pending / indexed / error
    added_at TEXT DEFAULT (datetime('now')),
    UNIQUE(kb_id, filename)
);
```

### 3.4 目录 + 概述自动生成

**触发时机：** 添加文件到知识库时

**实现：** 新建 `rag/kb_metadata.py`

```python
def generate_toc(content: str) -> dict:
    """LLM 提取文档标题层级结构。"""
    prompt = f"""请从以下文档中提取标题层级结构，输出 JSON 格式：
{{"title": "文档标题", "sections": [{{"title": "章节标题", "subsections": [...]}}, ...]}}

文档内容：
{content[:3000]}"""
    result = generate([{"role": "user", "content": prompt}])
    return json.loads(result)


def generate_summary(content: str) -> str:
    """LLM 生成文档概述。"""
    prompt = f"""请用 100-200 字概括以下文档的核心内容，包括：主题、覆盖范围、关键知识点。

文档内容：
{content[:2000]}"""
    return generate([{"role": "user", "content": prompt}])
```

**改动文件：**
- `rag/kb_metadata.py` — 新建
- `rag/knowledge_base.py` — `add_document()` 中调用生成
- `rag/api.py` — 新增端点

---

## 4. 已知 Bug 修复

| Bug | 文件 | 修复 |
|-----|------|------|
| `/data` 挂载暴露敏感文件 | api.py | ✅ 已修复 |
| `update_message` 无权限校验 | user_db.py | ✅ 已修复 |
| XSS via v-html | ChatView.vue | ✅ 已修复（DOMPurify） |
| SQL 注入可绕过 | tools.py | ✅ 已修复（PRAGMA query_only） |
| Auth 方案混乱 | auth.py | ✅ 已修复（JWT + API Key 双认证） |
| SSE 缺少响应头 | api.py | ✅ 已修复 |
| SSE 解析器丢 token | chat.ts | ✅ 已修复（行缓冲） |
| fetchUser 误登出 | auth.ts | ✅ 已修复 |
| 点击文件页显示 JSON | api.py | ✅ 已修复（SPA fallback） |
| 页面标题不切换 | MainLayout.vue | 需要实现 |
| 反馈按钮没调 API | chat.ts | ✅ 已修复 |
| 知识库页 auth header 错误 | KnowledgeView.vue | ✅ 已修复 |
| regenerate 没调 API | chat.ts | ✅ 已修复 |

---

## 5. 实现顺序

| 阶段 | 内容 | 工作量 |
|------|------|--------|
| **阶段 1** | 前端布局重构（侧边栏导航、用户右上角、页面标题） | 1 天 |
| **阶段 2** | 流式聊天 + 反馈 + 追问前端对接 | 1 天 |
| **阶段 3** | 侧边栏文件选择器 + 检索范围状态 | 1 天 |
| **阶段 4** | 知识库后端扩展（目录/概述生成、详情端点） | 1 天 |
| **阶段 5** | 知识库前端（列表页、详情页、文件管理） | 2 天 |
| **阶段 6** | 对话标题 + 侧边栏折叠 + 细节打磨 | 1 天 |

**总计：约 7 天**

---

## 6. 测试目标

| 阶段 | 新增测试 | 累计 |
|------|---------|------|
| 阶段 1-3 | +10（前端交互测试） | 314 |
| 阶段 4 | +15（kb_metadata 测试） | 329 |
| 阶段 5-6 | +5 | 334 |

**目标：330+ 测试全过**
