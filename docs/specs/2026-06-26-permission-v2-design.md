# 知识库与文件权限系统设计文档

> 版本：v1.0
> 日期：2026-06-26
> 状态：设计中

---

## 一、背景与目标

### 现有问题

1. **知识库无权限控制** — 任何登录用户可创建/删除/修改所有 KB（C10）
2. **文件权限只有两档** — 公开/私有，无法实现"部门内共享"场景
3. **共享机制不统一** — 文件有 `document_shares` 表，KB 无共享机制
4. **下载权限未控制** — 能看到就能下载，无法"可预览不可下载"

### 设计目标

- 统一文件和知识库的权限模型
- 支持企业/学校内部使用场景（部门共享、项目组协作）
- 最小改动，复用现有表结构
- 分阶段实现，每阶段可独立上线

---

## 二、权限模型

### 2.1 三档可见范围（scope）

| scope | 含义 | 适用场景 |
|-------|------|---------|
| `private` | 仅 owner 可见 | 个人草稿、机密文档 |
| `shared` | owner + 指定用户可见 | 部门知识库、项目组资料 |
| `public` | 所有登录用户可见 | 公司公共库、课程资料 |

### 2.2 共享权限级别（permission）

当 `scope='shared'` 时，共享给指定用户的权限级别：

| permission | 含义 | 适用场景 |
|------------|------|---------|
| `view` | 仅查看/查询/下载 | 学生查看课程资料 |
| `edit` | 可查看 + 可修改概述/目录/标签 | 教师编辑课程资料 |

### 2.3 特殊标记

| 标记 | 含义 | 权限影响 |
|------|------|---------|
| `protected` | 仓库文件（git 同步） | 始终 public，不可删除，不可修改 scope |
| `owner_id=0` | 系统所有 | admin 可管理 |

### 2.4 权限判定规则

```
判定顺序（短路求值）：
1. admin → 放行（所有操作）
2. protected 文件 → public 放行（查看/下载），不可修改/删除
3. scope = 'public' → 放行（查看/下载/查询）
4. owner = 当前用户 → 放行（所有操作）
5. scope = 'shared' && 在 shares 表中：
   - permission = 'view' → 放行（查看/下载/查询）
   - permission = 'edit' → 放行（查看/下载/查询 + 修改概述/目录/标签）
6. 其他 → 拒绝
```

---

## 三、操作权限矩阵

### 3.1 文件操作

| 操作 | private | shared (view) | shared (edit) | public | protected | admin |
|------|---------|---------------|---------------|--------|-----------|-------|
| 查看/列出 | owner | owner + 共享用户 | owner + 共享用户 | 所有人 | 所有人 | ✅ |
| 下载（若 downloadable=true） | owner | owner + 共享用户 | owner + 共享用户 | 所有人 | 所有人 | ✅ |
| 下载（若 downloadable=false） | owner | owner | owner | owner | admin only | ✅ |
| 切换 scope | owner | owner | owner | owner | ❌ | ✅ |
| 修改标签/概述 | owner | ❌ | owner + 共享(edit) | owner | ❌ | ✅ |
| 删除 | owner | owner | owner | owner | ❌ | ✅ |
| 共享给他人 | owner | owner | owner | - | - | ✅ |

### 3.2 知识库操作

| 操作 | private | shared (view) | shared (edit) | public | 无 owner（旧 KB） | admin |
|------|---------|---------------|---------------|--------|------------------|-------|
| 查看/列出 | owner | owner + 共享用户 | owner + 共享用户 | 所有人 | 所有人 | ✅ |
| 查询（问答） | owner | owner + 共享用户 | owner + 共享用户 | 所有人 | 所有人 | ✅ |
| 添加/移除文档 | owner | owner | owner + 共享(edit) | owner | ❌ | ✅ |
| 修改概述/目录 | owner | ❌ | owner + 共享(edit) | owner | ❌ | ✅ |
| 切换 scope | owner | owner | owner | owner | ❌ | ✅ |
| 重命名 | owner | owner | owner | owner | ❌ | ✅ |
| 删除 | owner | owner | owner | owner | ❌ | ✅ |
| 共享给他人 | owner | owner | owner | - | - | ✅ |

---

## 四、数据模型

### 4.1 现有表变更

#### document_permissions（改字段）

```sql
-- 新增 scope 列，替代 is_public
ALTER TABLE document_permissions ADD COLUMN scope TEXT DEFAULT 'private';

-- 迁移数据
UPDATE document_permissions SET scope = 'public' WHERE is_public = 1;
UPDATE document_permissions SET scope = 'private' WHERE is_public = 0;
-- protected 文件强制 public
UPDATE document_permissions SET scope = 'public' WHERE protected = 1;

-- is_public 列保留但废弃（兼容旧代码，后续移除）

-- 索引：按 scope 过滤是高频操作
CREATE INDEX IF NOT EXISTS idx_doc_perm_scope ON document_permissions(scope);
```

#### document_shares（加字段）

```sql
-- 新增 permission 列
ALTER TABLE document_shares ADD COLUMN permission TEXT DEFAULT 'view';
-- 可选值：'view'（仅查看）、'edit'（可编辑）
```

#### kb_metadata（加字段）

```sql
-- 新增 owner_id 和 scope
ALTER TABLE kb_metadata ADD COLUMN owner_id INTEGER DEFAULT 0;  -- 默认系统 ID
ALTER TABLE kb_metadata ADD COLUMN scope TEXT DEFAULT 'private';

-- 旧数据迁移
UPDATE kb_metadata SET owner_id = 0, scope = 'public' WHERE user_id IS NULL;
UPDATE kb_metadata SET owner_id = user_id, scope = 'private' WHERE user_id IS NOT NULL;

-- user_id 列：Phase 1 保留（兼容），Phase 2 废弃（代码不再读取）

-- 索引
CREATE INDEX IF NOT EXISTS idx_kb_meta_owner ON kb_metadata(owner_id);
CREATE INDEX IF NOT EXISTS idx_kb_meta_scope ON kb_metadata(scope);
```

### 4.2 新增表

#### kb_shares

```sql
CREATE TABLE IF NOT EXISTS kb_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    permission TEXT DEFAULT 'view',  -- 'view' 或 'edit'
    granted_by INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(kb_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE CASCADE
    -- kb_id 无外键约束（Qdrant 集合不在 SQLite 中），KB 删除时由应用层清理
);

CREATE INDEX IF NOT EXISTS idx_kb_shares_user ON kb_shares(user_id);
CREATE INDEX IF NOT EXISTS idx_kb_shares_kb ON kb_shares(kb_id);
```

### 4.3 E-R 图

```
users
  │
  ├──── owner_id ────┬──── document_permissions ──── document_shares
  │                  │         (scope, protected)      (permission)
  │                  │
  └──── owner_id ────┴──── kb_metadata ────────────── kb_shares
                            (scope)                    (permission)
```

---

## 五、API 设计

### 5.1 新增端点

```
# 知识库共享管理
POST   /knowledge-bases/{kb_id}/share          # 共享给指定用户
DELETE /knowledge-bases/{kb_id}/share/{uid}     # 取消共享
GET    /knowledge-bases/{kb_id}/shares          # 查看共享列表

# 文件共享管理（已有，复用）
POST   /documents/{doc_id}/share               # 共享给指定用户
DELETE /documents/{doc_id}/share/{uid}          # 取消共享
GET    /documents/{doc_id}/shares               # 查看共享列表
```

### 5.2 修改端点

```
# 知识库端点（加 owner/scope 检查）
POST   /knowledge-bases           # 创建 → 存 owner_id + scope
DELETE /knowledge-bases/{kb_id}   # 删除 → 仅 owner/admin
PUT    .../name                   # 重命名 → 仅 owner/admin
PUT    .../overview               # 概述 → 仅 owner/admin/shared(edit)
PUT    .../documents/{doc}/toc    # 目录 → 仅 owner/admin/shared(edit)
POST   .../documents              # 添加文档 → 仅 owner/admin/shared(edit)
DELETE .../documents/{doc}        # 移除文档 → 仅 owner/admin

# 文件端点（scope 替代 is_public）
PUT    /files/{filename}/visibility  # 切换 scope（private/shared/public）
GET    /files                        # 列出 → 按 scope + shares 过滤
```

#### CREATE KB 请求体变更

```json
// 方案 B：创建时可选 scope，默认 private
{ "name": "技术文档库", "scope": "public" }  // scope 可选

// 后端处理：
// 1. scope 不传 → 默认 'private'
// 2. scope 无效 → 400
// 3. 存入 kb_metadata(kb_id, name, owner_id=current_user, scope)
```

#### DELETE KB owner 检查逻辑

```python
# 现在：无 owner 检查
async def delete_knowledge_base(kb_id: str, user_id: str = Security(verify_api_key)):

# Phase 1 后：加 owner 检查
async def delete_knowledge_base(kb_id: str, authorization: str = Header(default="")):
    user_dict = await _require_auth(authorization)
    kb = get_kb_metadata(kb_id)
    if not kb:
        raise 404
    if not user_dict["is_admin"] and kb["owner_id"] != user_dict["id"]:
        raise 403  # 非 owner 且非 admin
    # 继续删除逻辑
```

#### KB 列出响应变更

```json
// 现在
[{ "kb_id": "kb_xxx", "name": "...", "doc_count": 12 }]

// Phase 1 后
[{ "kb_id": "kb_xxx", "name": "...", "doc_count": 12, "scope": "public", "is_owner": true }]
```

### 5.3 共享请求体

```json
// POST /knowledge-bases/{kb_id}/share
{
    "user_id": 3,
    "permission": "view"  // 或 "edit"
}

// POST /documents/{doc_id}/share
{
    "user_id": 3,
    "permission": "view"  // 或 "edit"
}
```

---

## 六、前端设计

### 6.1 文件列表

```
┌─────────────────────────────────────────────────────┐
│  [全部] [默认] [私有] [共享] [公开]    [+ 上传]      │
├─────────────────────────────────────────────────────┤
│  📄 压测.md        [公开·默认]           ⋯           │
│  📄 运维手册.pdf   [共享: 张三,李四]     ⋯           │
│  📄 会议记录.docx  [私有]                ⋯           │
└─────────────────────────────────────────────────────┘
```

### 6.2 知识库列表

```
┌─────────────────────────────────────────────────────┐
│  [+ 创建知识库]                                      │
├─────────────────────────────────────────────────────┤
│  📚 技术文档库    [公开]  12篇文档    ⋯              │
│  📚 项目A资料     [共享: 3人]  5篇文档  ⋯            │
│  📚 个人笔记      [私有]  3篇文档    ⋯              │
└─────────────────────────────────────────────────────┘
```

### 6.3 共享对话框

```
┌─────────────────────────────────────────┐
│  共享：运维手册.pdf                      │
├─────────────────────────────────────────┤
│  🔍 搜索用户...                         │
│                                         │
│  已共享：                                │
│  ┌─────────────────────────────────┐   │
│  │ 张三  [可查看 ▾]    [移除]       │   │
│  │ 李四  [可编辑 ▾]    [移除]       │   │
│  └─────────────────────────────────┘   │
│                                         │
│  可见范围：                              │
│  ○ 私有  ○ 共享  ○ 公开                 │
│                                         │
│       [取消]  [保存]                     │
└─────────────────────────────────────────┘
```

### 6.4 下载控制（Phase 3）

```
文件详情页：
┌─────────────────────────────────────────┐
│  运维手册.pdf                            │
│  大小: 2.3 MB  上传者: 张三              │
│  可见范围: 公开                          │
│  允许下载: ✅                            │
│                                         │
│  [预览]  [下载]  [共享]  [删除]          │
└─────────────────────────────────────────┘

若 downloadable=false：
┌─────────────────────────────────────────┐
│  [预览]  [下载 - 灰色禁用]  [共享]       │
└─────────────────────────────────────────┘
```

---

## 七、迁移策略

### 7.1 数据迁移

```python
# 一次性迁移脚本（启动时执行，幂等）
def migrate_permissions():
    # 1. document_permissions: is_public → scope
    db.execute("""
        UPDATE document_permissions
        SET scope = CASE
            WHEN protected = 1 THEN 'public'
            WHEN is_public = 1 THEN 'public'
            ELSE 'private'
        END
        WHERE scope IS NULL
    """)

    # 2. kb_metadata: 旧 KB 迁移
    # user_id IS NULL → owner_id=0（系统 ID）, scope='public'
    db.execute("""
        UPDATE kb_metadata
        SET owner_id = 0, scope = 'public'
        WHERE user_id IS NULL AND scope IS NULL
    """)
    # user_id 有值 → owner_id=user_id, scope='private'（保守默认）
    db.execute("""
        UPDATE kb_metadata
        SET owner_id = user_id, scope = 'private'
        WHERE user_id IS NOT NULL AND scope IS NULL
    """)

    # 3. document_shares: 加 permission 列（默认 'view'）
    # ALTER TABLE 已在 schema 升级中处理
```

### 7.2 向后兼容

| 场景 | 处理方式 |
|------|---------|
| 旧代码读 is_public | 字段保留，Phase 1 文件代码继续读 is_public |
| 旧 KB 无 owner_id | owner_id=0（系统 ID），scope='public'，所有人可见 |
| 旧 document_shares 无 permission | 默认 'view' |
| protected 文件 | 强制 scope='public'，不可修改 |
| Phase 1 文件代码 | 读 is_public，不读 scope（向后兼容） |
| Phase 2 文件代码 | 切换到读 scope，is_public 废弃 |

---

## 八、分阶段实现

### Phase 1：KB owner + 字段统一 + 两档逻辑

**目标：** 解决 C10（KB 无权限控制），字段设计统一，最小改动上线

**决策记录：**
- scope 字段直接用三档 TEXT（private/shared/public），Phase 1 只处理 private/public
- 旧 KB owner_id = 0（系统保留 ID），scope = 'public'
- 字段设计现在统一（KB + 文件都加 scope 列），代码逻辑分阶段切换

**改动：**
- kb_metadata 加 `owner_id`、`scope`（默认 'private'）
- document_permissions 加 `scope` 列（迁移 is_public 数据，Phase 1 文件代码继续读 is_public）
- 创建 KB 时存 owner_id + scope
- 删除/修改 KB 端点加 owner 检查
- 查询/列出 KB 按 scope 过滤（规则见下）
- 前端：KB 列表显示 scope 标签

**KB 列出/查询过滤规则（Phase 1）：**

| 条件 | 可见 |
|------|------|
| admin | 所有 KB |
| scope='public' | 所有人 |
| scope='private' && owner_id=当前用户 | 仅 owner |
| owner_id=0（旧数据） | 所有人（向后兼容） |

**数据迁移：**
```sql
-- kb_metadata
UPDATE kb_metadata SET owner_id = 0, scope = 'public' WHERE user_id IS NULL;
UPDATE kb_metadata SET owner_id = user_id, scope = 'private' WHERE user_id IS NOT NULL;

-- document_permissions（加 scope 列，文件代码暂不读）
UPDATE document_permissions SET scope = 'public' WHERE is_public = 1;
UPDATE document_permissions SET scope = 'private' WHERE is_public = 0;
UPDATE document_permissions SET scope = 'public' WHERE protected = 1;
```

**不改：**
- 文件权限代码不动（继续读 is_public，Phase 2 切换到 scope）
- 不加共享机制
- 不加下载控制

### Phase 2：shared 档 + 共享机制

**目标：** 支持"部门/项目组内共享"场景

**改动：**
- document_permissions 加 `scope` 列替代 is_public
- document_shares 加 `permission` 列（view/edit）
- 新建 kb_shares 表
- 权限判定逻辑重写为三档 + permission
- 新增共享管理 API 端点
- 前端：共享对话框（含用户搜索）
- 数据迁移脚本

### Phase 3：下载控制 + 企业级功能

**目标：** 支持"可预览不可下载"等企业级需求

**改动：**
- document_permissions 加 `downloadable` 列（默认 true）
- 下载端点检查 downloadable + scope + permission
- 前端：下载按钮按权限显示/禁用
- 可选：KB 级别的 downloadable 设置

---

## 九、测试计划

### Phase 1 测试

| 测试项 | 预期 |
|--------|------|
| 创建 KB → owner_id 写入 | ✅ |
| 非 owner 删除 KB → 403 | ✅ |
| admin 删除任意 KB → 200 | ✅ |
| 旧 KB（user_id=NULL）→ public | ✅ |
| 私有 KB 对非 owner 不可见 | ✅ |
| 公开 KB 对所有人可见 | ✅ |

### Phase 2 测试

| 测试项 | 预期 |
|--------|------|
| 共享文件给用户(view) → 可查看不可编辑 | ✅ |
| 共享文件给用户(edit) → 可查看+可编辑 | ✅ |
| 取消共享 → 用户不可见 | ✅ |
| 共享 KB 给用户(view) → 可查询 | ✅ |
| 共享 KB 给用户(edit) → 可查询+可编辑概述 | ✅ |
| scope 切换 private→shared→public | ✅ |
| protected 文件 → 始终 public 不可改 | ✅ |
| 数据迁移：is_public=1 → scope='public' | ✅ |
| 数据迁移：旧 shares → permission='view' | ✅ |

### Phase 3 测试

| 测试项 | 预期 |
|--------|------|
| downloadable=true → 可下载 | ✅ |
| downloadable=false → 不可下载 | ✅ |
| admin 可下载所有文件 | ✅ |
| owner 可下载自己的文件 | ✅ |

---

## 十、风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 迁移脚本破坏旧数据 | 低 | 高 | 迁移前备份 data/ 目录 |
| 三档逻辑复杂导致 bug | 中 | 中 | Phase 1 先上两档验证 |
| 前端共享对话框工作量大 | 中 | 低 | Phase 2 再做 |
| downloadable 和 scope 组合爆炸 | 低 | 低 | 只在文件级别控制，KB 不加 |
