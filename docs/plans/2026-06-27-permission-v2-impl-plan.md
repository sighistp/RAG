# 权限 v2 实施计划

> 设计文档：`docs/specs/2026-06-26-permission-v2-design.md`
> 日期：2026-06-27
> 原则：TDD，每阶段可独立上线

---

## 决策汇总

| # | Phase | 问题 | 决策 |
|---|-------|------|------|
| D1 | 1 | scope 字段 | 三档 TEXT（private/shared/public），Phase 1 只处理 private/public |
| D2 | 1 | 旧 KB owner | owner_id=0（系统 ID），scope='public' |
| D3 | 1 | 字段统一 | document_permissions + kb_metadata 现在都加 scope 列，代码分阶段切换 |
| D4 | 1 | owner_id DEFAULT | INTEGER DEFAULT 0 |
| D5 | 1 | CREATE KB | `{ "name": "...", "scope": "public" }`，scope 可选，默认 private |
| D6 | 1 | DELETE KB | `_require_auth` + owner 检查 |
| D7 | 1 | KB 列出响应 | 返回 scope + is_owner |
| D8 | 2 | 用户搜索 | `GET /users?q=xxx`，所有登录用户可用，q≥2，最多 20 条，只返回 id+username |
| D9 | 2 | scope 切换 | owner/admin 可切，shared→public→private 时清除 shares |
| D10 | 2 | shared 显示 | 混在列表，标签 [共享: 张三]，筛选加"共享给我" |
| D11 | 2 | schema 变更 | document_shares 加 permission 列 + 新建 kb_shares 表 |
| D12 | 3 | 下载端点 | `GET /files/{name}/download`，检查 downloadable + scope + permission |
| D13 | 3 | 前端控制 | 灰色禁用 + tooltip |
| D14 | 3 | KB downloadable | 暂不做 |

---

## Phase 1：KB owner + 字段统一 + 两档逻辑

### 目标
解决 C10（KB 无权限控制），字段设计统一，最小改动上线。

### Task 1.1：数据库迁移

**改动：**
- kb_metadata 加 `owner_id INTEGER DEFAULT 0`、`scope TEXT DEFAULT 'private'`
- document_permissions 加 `scope TEXT DEFAULT 'private'`
- 迁移旧数据

**测试：**
- 旧 KB（user_id=NULL）→ owner_id=0, scope='public'
- 旧 KB（user_id 有值）→ owner_id=user_id, scope='private'
- document_permissions: is_public=1 → scope='public'
- document_permissions: protected=1 → scope='public'

**文件：** `rag/user_db.py`

### Task 1.2：KB CRUD 支持 owner/scope

**改动：**
- `KnowledgeBaseManager.create_kb()` 接受 owner_id + scope 参数
- `user_db` 新增 `get_kb_metadata()`、`set_kb_owner()`、`update_kb_scope()` 方法
- 创建 KB 时存入 kb_metadata

**测试：**
- 创建 KB → owner_id 写入
- 创建 KB → scope 默认 'private'
- 创建 KB → scope='public' 显式指定

**文件：** `rag/knowledge_base.py`、`rag/user_db.py`

### Task 1.3：KB 列出按 scope 过滤

**改动：**
- `GET /knowledge-bases` 端点按 scope + owner 过滤
- 返回 scope + is_owner 字段

**测试：**
- admin 看到所有 KB
- 普通用户看到 public KB + 自己的 private KB
- 旧 KB（owner_id=0）所有人可见
- 响应包含 scope + is_owner

**文件：** `rag/api.py`

### Task 1.4：KB 删除/修改加 owner 检查

**改动：**
- DELETE /knowledge-bases/{kb_id} → 仅 owner/admin
- PUT .../overview → 仅 owner/admin
- PUT .../documents/{doc}/toc → 仅 owner/admin
- POST .../documents → 仅 owner/admin
- DELETE .../documents/{doc} → 仅 owner/admin

**测试：**
- owner 删除自己的 KB → 200
- 非 owner 删除他人 KB → 403
- admin 删除任意 KB → 200
- 旧 KB（owner_id=0）→ admin 可删，普通用户不可

**文件：** `rag/api.py`

### Task 1.5：KB 查询按 scope 过滤

**改动：**
- POST /knowledge-bases/{kb_id}/query → 检查 scope 权限
- private KB 只有 owner/admin 可查询

**测试：**
- owner 查询自己的 private KB → 200
- 非 owner 查询 private KB → 403
- 任何人查询 public KB → 200

**文件：** `rag/api.py`

### Task 1.6：前端 KB scope 标签

**改动：**
- KB 列表显示 scope 标签（私有/公开）
- 创建 KB 时可选 scope
- KB 操作按钮按权限显示

**测试：** 手动测试

**文件：** `frontend/src/views/KBModeView.vue`、`frontend/src/views/KnowledgeDetailView.vue`

### Phase 1 全量回归

- 500+ 测试全过
- 手动验证：创建/删除/查询 KB 权限正确

---

## Phase 2：shared 档 + 共享机制

### 目标
支持"部门/项目组内共享"场景。

### Task 2.1：kb_shares 表 + document_shares 加 permission 列

**改动：**
- 新建 kb_shares 表
- document_shares 加 `permission TEXT DEFAULT 'view'`

**测试：**
- kb_shares 表创建成功
- document_shares 加列成功
- 旧 shares 记录 permission 默认 'view'

**文件：** `rag/user_db.py`

### Task 2.2：用户搜索 API

**改动：**
- `GET /users?q=xxx` 端点
- 所有登录用户可用
- q≥2 字符，最多 20 条，只返回 id+username

**测试：**
- 登录用户搜索 → 返回结果
- 未登录 → 401
- q<2 → 400
- 结果最多 20 条
- 只含 id + username

**文件：** `rag/api.py`

### Task 2.3：文件共享 API

**改动：**
- POST /files/{filename}/share → 共享给指定用户
- DELETE /files/{filename}/share/{uid} → 取消共享
- GET /files/{filename}/shares → 查看共享列表

**测试：**
- owner 共享文件 → 200
- 非 owner 共享 → 403
- 重复共享 → 409
- 取消共享 → 200
- 查看共享列表 → 返回用户列表

**文件：** `rag/api.py`

### Task 2.4：KB 共享 API

**改动：**
- POST /knowledge-bases/{kb_id}/share
- DELETE /knowledge-bases/{kb_id}/share/{uid}
- GET /knowledge-bases/{kb_id}/shares

**测试：** 同 Task 2.3

**文件：** `rag/api.py`

### Task 2.5：权限判定重写为三档

**改动：**
- `check_doc_permission` 支持 scope 三档 + permission
- `check_kb_permission` 新增
- 文件端点切换到读 scope（废弃 is_public）

**测试：**
- private 文件：owner 可看，其他人不可
- shared 文件（view）：共享用户可看不可编辑
- shared 文件（edit）：共享用户可看可编辑
- public 文件：所有人可看
- protected 文件：始终 public 不可改

**文件：** `rag/permissions.py`

### Task 2.6：scope 切换逻辑

**改动：**
- PUT /files/{filename}/scope → 切换 scope
- PUT /knowledge-bases/{kb_id}/scope → 切换 scope
- shared→public 或 shared→private 时清除 shares

**测试：**
- private→shared → 成功
- shared→private → shares 被清除
- shared→public → shares 被清除
- protected 文件 → 不可切换

**文件：** `rag/api.py`

### Task 2.7：前端共享对话框

**改动：**
- 共享对话框组件（用户搜索 + 权限选择 + 共享列表）
- 文件/KB 操作菜单加"共享给..."
- 列表标签显示 [共享: 张三]
- 筛选标签加"共享给我"

**测试：** 手动测试

**文件：** `frontend/src/components/ShareDialog.vue`、`frontend/src/views/FileModeView.vue`

### Phase 2 全量回归

- 600+ 测试全过
- 手动验证：共享/取消共享/权限判定正确

---

## Phase 3：下载控制

### 目标
支持"可预览不可下载"企业级需求。

### Task 3.1：downloadable 字段

**改动：**
- document_permissions 加 `downloadable INTEGER DEFAULT 1`
- 创建文件时默认 downloadable=1

**测试：**
- 新文件默认可下载
- 旧文件迁移后可下载

**文件：** `rag/user_db.py`

### Task 3.2：下载端点

**改动：**
- `GET /files/{filename}/download` 端点
- 检查 downloadable + scope + permission
- 返回 FileResponse + Content-Disposition: attachment

**测试：**
- downloadable=true → 200 + 文件
- downloadable=false + owner → 200 + 文件
- downloadable=false + 非 owner → 403
- admin 可下载所有文件

**文件：** `rag/api.py`

### Task 3.3：前端下载控制

**改动：**
- 文件列表：downloadable=false 时下载按钮灰色禁用 + tooltip
- 文件详情页：同上

**测试：** 手动测试

**文件：** `frontend/src/views/FileModeView.vue`

### Phase 3 全量回归

- 650+ 测试全过
- 手动验证：下载权限正确

---

## 执行顺序

```
Phase 1 (Task 1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 回归)
    ↓
Phase 2 (Task 2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 → 2.7 → 回归)
    ↓
Phase 3 (Task 3.1 → 3.2 → 3.3 → 回归)
```

每个 Phase 完成后可独立上线。
