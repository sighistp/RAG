# 权限管理系统设计文档

## 1. 概述

基于等级的知识库文档权限管理系统。核心规则：**用户等级 ≥ 文档等级** 且 **同一知识库内** 才可查看，辅以共享机制实现细粒度授权。

### 角色等级定义

| 等级 | 角色 | 说明 |
|------|------|------|
| 1 | 普通员工 | 默认等级 |
| 2 | 组长 | |
| 3 | 主管 | |
| 4 | 总监 | |
| 5 | 管理员（等级） | 最高等级，但不等于系统管理员 |
| — | 系统管理员 | `is_admin=true`，绕过所有权限限制 |

---

## 2. 权限规则

### 2.1 查看权限

满足以下**任一条件**即可查看文档：

| 条件 | 说明 |
|------|------|
| 等级 ≥ 文档等级 | 仅限同一知识库内 |
| 被文档所有者或管理员共享 | 即使等级不够也能看 |
| 系统管理员（`is_admin=true`） | 绕过所有限制 |

### 2.2 操作权限

| 操作 | 允许的用户 |
|------|-----------|
| 修改文档权限等级 | 文档上传者 或 系统管理员 |
| 共享文档 | 文档上传者 或 系统管理员 |
| 撤销共享 | 文档上传者 或 系统管理员 |
| 删除文档 | 文档上传者 或 系统管理员 |
| 被共享者再共享 | ❌ 不允许 |

### 2.3 查询模式

| scope | 说明 | 谁能用 |
|-------|------|--------|
| `accessible`（默认） | 返回：自己上传的 OR 被共享的 OR 等级够的 | 所有用户 |
| `all` | 返回该知识库全部文档 | 仅 `is_admin=true` |

> 系统管理员使用 `scope=accessible` 时，行为等同于 `scope=all`（自动绕过限制）。

---

## 3. 数据模型

### 3.1 users 表变更

```sql
ALTER TABLE users ADD COLUMN permission_level INTEGER DEFAULT 1;
ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;
```

### 3.2 document_permissions 表（新增）

记录每个文档的权限配置。

```sql
CREATE TABLE document_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_name TEXT NOT NULL,
    kb_id TEXT NOT NULL,
    owner_id INTEGER NOT NULL,          -- 上传者 user_id
    permission_level INTEGER DEFAULT 1, -- 1-5
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(doc_name, kb_id)             -- 同一知识库不允许同名文件
);

CREATE INDEX idx_doc_permissions_kb ON document_permissions(kb_id);
CREATE INDEX idx_doc_permissions_owner ON document_permissions(owner_id);
```

### 3.3 document_shares 表（新增）

记录文档的单独共享授权。

```sql
CREATE TABLE document_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,            -- 关联 document_permissions.id
    user_id INTEGER NOT NULL,           -- 被共享者
    granted_by INTEGER NOT NULL,        -- 授权人
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(doc_id, user_id),
    FOREIGN KEY (doc_id) REFERENCES document_permissions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES users(id)
);

CREATE INDEX idx_doc_shares_user ON document_shares(user_id);
CREATE INDEX idx_doc_shares_doc ON document_shares(doc_id);
```

### 3.4 数据关系图

```
users
  ├── permission_level (1-5)
  └── is_admin (bool)

document_permissions
  ├── doc_name + kb_id (UNIQUE)
  ├── owner_id → users.id
  └── permission_level (1-5)

document_shares
  ├── doc_id → document_permissions.id (CASCADE DELETE)
  ├── user_id → users.id (CASCADE DELETE)
  └── granted_by → users.id
```

---

## 4. API 设计

### 4.1 文档上传

#### `POST /upload` — 通用上传（不指定知识库）

```
Request:
  Content-Type: multipart/form-data
  file: <binary>
  permission_level: 1

Response 201:
  { "id": 1, "doc_name": "report.pdf", "permission_level": 1 }

Response 400:
  { "detail": "permission_level 必须在 1-5 之间" }
```

#### `POST /knowledge-bases/{kb_id}/documents` — 上传到指定知识库

```
Request:
  Content-Type: multipart/form-data
  file: <binary>
  permission_level: 2

Response 201:
  { "id": 2, "doc_name": "report.pdf", "kb_id": "ops", "permission_level": 2 }

Response 400:
  { "detail": "permission_level 必须在 1-5 之间" }

Response 409:
  { "detail": "文件 report.pdf 在该知识库中已存在" }
```

### 4.2 文档权限管理

#### `PUT /documents/{doc_id}/permission` — 修改权限等级

```
Request:
  { "permission_level": 3 }

Response 200:
  { "id": 2, "permission_level": 3 }

Response 403:
  { "detail": "仅文档上传者或管理员可修改权限" }
```

#### `GET /documents/{doc_id}/permissions` — 查看文档权限信息

```
Response 200:
  {
    "doc_id": 2,
    "doc_name": "report.pdf",
    "permission_level": 3,
    "owner": { "id": 1, "username": "alice" },
    "shared_with": [
      { "id": 5, "username": "bob", "granted_by": 1, "granted_at": "2026-06-21T10:00:00" }
    ]
  }
```

### 4.3 文档共享

#### `POST /documents/{doc_id}/share` — 共享给指定用户

```
Request:
  { "user_id": 5 }

Response 201:
  { "doc_id": 2, "user_id": 5, "granted_by": 1 }

Response 403:
  { "detail": "仅文档上传者或管理员可共享" }

Response 409:
  { "detail": "该用户已被共享" }
```

#### `DELETE /documents/{doc_id}/share/{user_id}` — 撤销共享

```
Response 204: (无内容)

Response 403:
  { "detail": "仅文档上传者或管理员可撤销共享" }
```

### 4.4 知识库查询

#### `GET /knowledge-bases/{kb_id}/query` — 查询文档

```
Query Parameters:
  scope=accessible (默认) | all
  q=搜索关键词

scope=accessible 返回:
  - 自己上传的文档
  - 被共享的文档
  - 等级 >= 文档等级的文档

scope=all 返回:
  - 该知识库全部文档（仅管理员可用）

Response 200:
  {
    "documents": [
      {
        "id": 2,
        "doc_name": "report.pdf",
        "permission_level": 3,
        "owner": { "id": 1, "username": "alice" },
        "can_edit": true,
        "can_share": true,
        "size_human": "2.1 MB",
        "created_at": "2026-06-20T14:30:00"
      }
    ],
    "total": 1
  }
```

### 4.5 文档删除

#### `DELETE /documents/{doc_id}`

```
Response 204: (无内容)
```

> 删除时级联清理 `document_permissions` 和 `document_shares` 中的关联记录。

---

## 5. 查询逻辑（SQL 参考）

### scope=accessible 查询

```sql
SELECT DISTINCT dp.*
FROM document_permissions dp
LEFT JOIN document_shares ds ON ds.doc_id = dp.id AND ds.user_id = :current_user_id
WHERE dp.kb_id = :kb_id
  AND (
    dp.owner_id = :current_user_id           -- 自己上传的
    OR ds.id IS NOT NULL                      -- 被共享的
    OR :user_level >= dp.permission_level     -- 等级够的
  )
ORDER BY dp.created_at DESC;
```

### scope=all 查询（仅管理员）

```sql
SELECT dp.*
FROM document_permissions dp
WHERE dp.kb_id = :kb_id
ORDER BY dp.created_at DESC;
```

### 权限校验工具函数伪代码

```python
def check_doc_permission(doc_name: str, kb_id: str, user, action: str = "view"):
    """
    统一的文档权限校验工具函数（非中间件）。
    action: "view" | "edit" | "delete"
    返回 document_permission 记录，无权抛 HTTPException。
    """
    doc = get_document_permission_by_name(doc_name, kb_id)
    if not doc:
        raise HTTPException(404, "文档不存在")

    # 管理员绕过
    if user.is_admin:
        return doc

    if action == "view":
        if (doc.owner_id == user.id
            or is_shared(doc.id, user.id)
            or user.permission_level >= doc.permission_level):
            return doc
        raise HTTPException(403, "无权查看该文档")

    if action in ("edit", "delete"):
        if doc.owner_id == user.id:
            return doc
        raise HTTPException(403, "仅文档上传者或管理员可操作")
```

---

## 6. 前端变更

### 6.1 上传文件

- 上传弹窗新增**权限等级下拉**（1-5，默认 1）
- 上传到知识库时自动关联 `kb_id`

### 6.2 知识库查询

- 查询区域新增 **scope 选择器**（"我能看的" / "全部"，后者仅管理员可见）
- 搜索结果展示权限元数据（等级、上传者、是否可编辑）

### 6.3 文档详情

- 显示权限等级标签
- 显示共享状态及共享用户列表
- 提供"修改权限"和"共享"操作入口

---

## 7. 实现阶段

| 阶段 | 文件 | 内容 | 依赖 |
|------|------|------|------|
| 1 | `user_db.py` | 建 `document_permissions` + `document_shares` 表，`users` 表加 `permission_level` / `is_admin` 字段 | 无 |
| 2 | `rag/permissions.py`（新建） | `check_doc_permission()` 工具函数 | 阶段1 |
| 2 | `rag/api.py` | `DELETE /files/{filename}` 加权限校验 | 阶段1 |
| 2 | `rag/api.py` | `POST /files/{filename}/tags` 加权限校验 | 阶段1 |
| 2 | `rag/api.py` | `DELETE /knowledge-bases/{kb_id}/documents/{doc_name}` 加权限校验 | 阶段1 |
| 3 | `rag/vector_store.py` | `add_to_collection()` payload 加 `doc_permission_id` 字段 | 阶段1 |
| 3 | `rag/pipeline.py` | 检索后过滤 + oversampling 逻辑（`top_k * 3` → 过滤 → 截取 `top_k`） | 阶段1 |
| 4 | `rag/auth.py` | 环境变量初始化 admin + `PUT /users/{id}/admin` 接口 | 阶段1 |
| 5 | 前端 | 上传权限选择器 + scope 选择器 + 共享管理界面 | 阶段2-4 |

---

## 8. 边界约定（留痕）

| 约定 | 决策 |
|------|------|
| 同知识库同名文件 | 拒绝上传，返回 409 |
| 被共享者能否再共享 | 不能，仅 owner 和 admin |
| 管理员等级限制 | 自动绕过，`is_admin=true` 等同于无限制 |
| 文档跨知识库 | 不允许，一个文档只属于一个知识库 |
| 知识库本身权限 | 不做，只控制文档级别 |
| 审计日志 | 暂不做，后续扩展 |
| 删除文档 | 级联清理 permissions + shares |
| 文档ID方案 | 保留自增 `id`，API 层用 `id` 操作，`doc_name + kb_id` 仅做业务约束 |
| 已有文档迁移 | 方案B：旧文档无权限记录则视为公开（level=1） |
| RAG检索权限过滤 | 检索后过滤（方案A） |
| 管理员初始化 | 环境变量 `INIT_ADMIN_USERNAME` + `PUT /users/{id}/admin` 接口双保险 |
| scope 选择器位置 | 仅知识库详情页，文件模式和分析模式不需要 |
| 批量导入权限 | 默认 level=1，可通过参数指定 |
| 文件模式权限 | 不变，文件模式是独立的个人文件，不走知识库权限 |

---

## 9. 已确认的实现细节

### 9.1 文档ID与Qdrant关联

- `document_permissions.id` 使用自增主键
- API 层统一用 `id` 操作文档权限
- **Qdrant payload 更新策略：**

| 时机 | 操作 |
|------|------|
| 新文档上传 `add_to_collection()` | payload 里加 `doc_permission_id` 字段 |
| `search()` 返回 | Qdrant 返回的 payload 已包含该字段，pipeline 直接用 |
| 旧文档 | 无 `doc_permission_id` 字段，pipeline 中视为公开 |

- `vector_store.py` 的 `add_to_collection()` 需支持写入 `doc_permission_id` 到 payload，`search()` 不需要改

### 9.2 已有文档处理策略

- 已有 Qdrant 向量不需要迁移（payload 无 `doc_permission_id`）
- 查询 `document_permissions` 时，如果某文档没有权限记录，视为公开（level=1）
- 仅新上传的文档才创建 `document_permissions` 记录

### 9.3 RAG 检索权限过滤

**职责划分：** `retriever.py` 只负责检索，`pipeline.py` 负责权限过滤编排。

**核心流程（改 `POST /query` 和 `/query/stream`）：**

```python
# pipeline.py 中 _prepare_context() 的权限过滤逻辑
raw_chunks = retriever.search(query, top_k=top_k * 3)   # 放大检索
allowed_chunks = filter_chunks_by_permission(raw_chunks, user)  # 权限过滤
final_chunks = allowed_chunks[:top_k]                     # 截取回 top_k
answer = llm.generate(query, final_chunks)
```

**filter_chunks_by_permission 逻辑：**

```python
def filter_chunks_by_permission(chunks, user):
    """过滤掉用户无权查看的文档的 chunks"""
    if user.is_admin:
        return chunks

    # 提取去重后的 doc_name 列表
    doc_names = set(c.doc_name for c in chunks)

    # 查 document_permissions，找出用户有权的文档
    allowed_docs = get_accessible_doc_names(doc_names, user)

    # 只保留有权文档的 chunks
    return [c for c in chunks if c.doc_name in allowed_docs]
```

**要点：**
- 检索时放大倍数（`top_k * 3`），过滤后再截取 `top_k`，避免过滤后结果过少
- 如果过滤后结果为空，返回"未找到相关内容"（不泄露文档存在）
- 旧文档无 `doc_permission_id` 记录，视为公开，直接放行
- 该逻辑写入 `pipeline.py` 的 `_prepare_context()` 中，紧接在 retrieve 之后、rerank 之前

### 9.4 管理员初始化

**首次部署：**
- 环境变量 `INIT_ADMIN_USERNAME` 指定初始管理员用户名
- 启动时检查是否有 admin，没有则根据环境变量自动设置

**后续管理：**
- `PUT /users/{id}/admin` 接口，需 admin 权限才能调用

### 9.5 现有接口的权限侵入范围

**统一使用 `check_doc_permission()` 工具函数**（不是中间件），各接口按需调用：

```python
# utils/permissions.py
def check_doc_permission(doc_name: str, kb_id: str, user, action: str = "view"):
    """
    action: "view" | "edit" | "delete"
    返回 document_permission 记录，无权抛 HTTPException
    """
```

**各接口调用方式：**

| 接口 | 调用方式 |
|------|----------|
| `DELETE /files/{filename}` | `check_doc_permission(filename, kb_id, current_user, action="delete")` |
| `POST /files/{filename}/tags` | `check_doc_permission(filename, kb_id, current_user, action="edit")` |
| `DELETE /knowledge-bases/{kb_id}/documents/{doc_name}` | `check_doc_permission(doc_name, kb_id, current_user, action="delete")` |
| `POST /query` / `POST /query/stream` | 不走 `check_doc_permission`，走 pipeline 中的检索后过滤逻辑 |

**为什么用工具函数不用中间件：** 中间件对所有路由生效，但有些路由（如 `/upload`、`/files` 列表）不需要文档级权限。工具函数按需调用，更灵活。

---

## 10. 前端变更补充

### 10.1 上传弹窗

- 新增**权限等级下拉**（1-5，默认 1）
- 批量导入时也可指定权限等级（默认 1）

### 10.2 知识库详情页

- 查询区域新增 **scope 选择器**（"我能看的" / "全部"，后者仅管理员可见）
- 搜索结果展示权限元数据（等级、上传者、是否可编辑）
- 文档详情显示权限等级标签 + 共享状态 + 共享用户列表
- 提供"修改权限"和"共享"操作入口（仅 owner 和 admin 可见）

### 10.3 文件模式 / 分析模式

- 不涉及权限变更，保持现有逻辑
