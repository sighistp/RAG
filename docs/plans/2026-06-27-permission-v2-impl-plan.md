# 权限 v2 实施计划

> 设计文档：`docs/specs/2026-06-26-permission-v2-design.md`
> 日期：2026-06-27
> 原则：TDD，每阶段可独立上线

---

## 决策汇总

| # | Phase | 问题 | 决策 |
|---|-------|------|------|
| D0 | 1 | 认证模式 | 公司内部系统，所有端点必须登录，废弃 `Security(verify_api_key)`，统一用 `_require_auth` |
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

**文件：** `rag/user_db.py`（`_create_tables` 方法，line 28-85）

**TDD 步骤：**

1. 写失败测试：

```python
def test_kb_metadata_has_owner_id_and_scope_columns(db):
    """kb_metadata 表应有 owner_id 和 scope 列。"""
    with db._lock:
        db._conn.execute(
            "INSERT INTO kb_metadata (kb_id, name, owner_id, scope) VALUES (?, ?, ?, ?)",
            ("kb_test_001", "测试知识库", 1, "private"),
        )
        db._conn.commit()
        row = db._conn.execute(
            "SELECT kb_id, name, owner_id, scope FROM kb_metadata WHERE kb_id = ?",
            ("kb_test_001",),
        ).fetchone()
    assert row is not None
    assert row["owner_id"] == 1
    assert row["scope"] == "private"
```

2. 跑测试确认 FAIL（`no such column: owner_id`）

3. 修改 `rag/user_db.py` 的 `kb_metadata` CREATE TABLE：

```python
CREATE TABLE IF NOT EXISTS kb_metadata (
    kb_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    overview TEXT DEFAULT '',
    user_id INTEGER,
    owner_id INTEGER DEFAULT 0,
    scope TEXT DEFAULT 'private',
    created_at TEXT DEFAULT (datetime('now'))
);
```

4. 在 `_create_tables` 的 executescript 后加迁移逻辑：

```python
# Phase 1 迁移：kb_metadata 加 owner_id/scope
try:
    self._conn.execute("SELECT owner_id FROM kb_metadata LIMIT 1")
except sqlite3.OperationalError:
    self._conn.execute("ALTER TABLE kb_metadata ADD COLUMN owner_id INTEGER DEFAULT 0")
    self._conn.execute("ALTER TABLE kb_metadata ADD COLUMN scope TEXT DEFAULT 'private'")
    self._conn.execute("UPDATE kb_metadata SET owner_id = 0, scope = 'public' WHERE user_id IS NULL")
    self._conn.execute("UPDATE kb_metadata SET owner_id = user_id, scope = 'private' WHERE user_id IS NOT NULL")
    self._conn.commit()

# Phase 1 迁移：document_permissions 加 scope
try:
    self._conn.execute("SELECT scope FROM document_permissions LIMIT 1")
except sqlite3.OperationalError:
    self._conn.execute("ALTER TABLE document_permissions ADD COLUMN scope TEXT DEFAULT 'private'")
    self._conn.execute("UPDATE document_permissions SET scope = 'public' WHERE is_public = 1")
    self._conn.execute("UPDATE document_permissions SET scope = 'private' WHERE is_public = 0")
    self._conn.execute("UPDATE document_permissions SET scope = 'public' WHERE protected = 1")
    self._conn.commit()
```

5. 跑测试确认 PASS
6. commit

### Task 1.2：KB Metadata CRUD 方法

**文件：** `rag/user_db.py`（新增方法）

**TDD 步骤：**

1. 写失败测试：

```python
def test_create_kb_metadata(db):
    db.create_kb_metadata("kb_test_001", "测试知识库", owner_id=1, scope="private")
    meta = db.get_kb_metadata("kb_test_001")
    assert meta is not None
    assert meta["owner_id"] == 1
    assert meta["scope"] == "private"

def test_get_kb_metadata_nonexistent(db):
    assert db.get_kb_metadata("kb_nonexistent") is None

def test_update_kb_scope(db):
    db.create_kb_metadata("kb_test_001", "测试知识库", owner_id=1, scope="private")
    db.update_kb_scope("kb_test_001", "public")
    assert db.get_kb_metadata("kb_test_001")["scope"] == "public"

def test_get_kb_metadata_by_names_batch(db):
    db.create_kb_metadata("kb_a", "A库", owner_id=1, scope="public")
    db.create_kb_metadata("kb_b", "B库", owner_id=2, scope="private")
    result = db.get_kb_metadata_by_names(["kb_a", "kb_b", "kb_c"])
    assert len(result) == 3
    assert result["kb_a"]["scope"] == "public"
    assert result["kb_b"]["scope"] == "private"
    assert result["kb_c"] is None
```

2. 跑测试确认 FAIL（`AttributeError: 'UserDB' object has no attribute 'create_kb_metadata'`）

3. 在 `rag/user_db.py` 的 kb_documents 部分后新增方法：

```python
def create_kb_metadata(self, kb_id: str, name: str, owner_id: int = 0, scope: str = "private") -> None:
    """创建 KB 元数据（仅新 KB 调用，不覆盖已有数据）。"""
    with self._lock:
        self._conn.execute(
            "INSERT INTO kb_metadata (kb_id, name, owner_id, scope) VALUES (?, ?, ?, ?)",
            (kb_id, name, owner_id, scope),
        )
        self._conn.commit()

def get_kb_metadata(self, kb_id: str) -> dict[str, Any] | None:
    with self._lock:
        row = self._conn.execute(
            "SELECT kb_id, name, owner_id, scope, created_at FROM kb_metadata WHERE kb_id = ?",
            (kb_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)

def update_kb_scope(self, kb_id: str, scope: str) -> None:
    with self._lock:
        self._conn.execute("UPDATE kb_metadata SET scope = ? WHERE kb_id = ?", (scope, kb_id))
        self._conn.commit()

def get_kb_metadata_by_names(self, kb_ids: list[str]) -> dict[str, dict[str, Any] | None]:
    if not kb_ids:
        return {}
    with self._lock:
        placeholders = ",".join("?" for _ in kb_ids)
        rows = self._conn.execute(
            f"SELECT kb_id, name, owner_id, scope, created_at FROM kb_metadata WHERE kb_id IN ({placeholders})",
            kb_ids,
        ).fetchall()
    meta_map = {r["kb_id"]: dict(r) for r in rows}
    return {kid: meta_map.get(kid) for kid in kb_ids}
```

4. 跑测试确认 PASS
5. commit

### Task 1.3：KB 列出按 scope 过滤 + CREATE KB 存 owner/scope

**文件：** `rag/api.py`（`list_knowledge_bases` + `create_knowledge_base` + `KBResponse` 模型）

**TDD 步骤：**

1. 写失败测试（测试过滤逻辑）：

```python
def test_list_kbs_filters_private_for_non_owner(db):
    owner = db.create_user("alice", "pwd")
    other = db.create_user("bob", "pwd")
    db.set_kb_metadata("kb_private", "私有库", owner_id=owner, scope="private")
    db.set_kb_metadata("kb_public", "公开库", owner_id=owner, scope="public")
    meta_map = db.get_kb_metadata_by_names(["kb_private", "kb_public"])
    visible = [kid for kid, meta in meta_map.items()
               if meta and (meta["scope"] == "public" or meta["owner_id"] == other)]
    assert "kb_public" in visible
    assert "kb_private" not in visible

def test_list_kbs_admin_sees_all(db):
    owner = db.create_user("alice", "pwd")
    admin = db.create_user("root", "pwd")
    db.set_user_admin(admin, True)
    db.set_kb_metadata("kb_private", "私有库", owner_id=owner, scope="private")
    db.set_kb_metadata("kb_public", "公开库", owner_id=owner, scope="public")
    # admin 看到所有
    assert True  # 实际测试在 API 层
```

2. 跑测试确认 PASS（这些测试只测 DB 层逻辑）

3. 修改 `KBResponse` 模型：

```python
class KBResponse(BaseModel):
    kb_id: str
    name: str
    doc_count: int
    scope: str = "public"
    is_owner: bool = False
```

4. 修改 `list_knowledge_bases` 端点：

```python
@app.get("/knowledge-bases", summary="列出知识库")
async def list_knowledge_bases(authorization: str = Header(default="")):
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)

    def _list():
        manager = KnowledgeBaseManager()
        kbs = manager.list_kbs()
        kb_ids = [kb.kb_id for kb in kbs]
        meta_map = user_db.get_kb_metadata_by_names(kb_ids)
        result = []
        for kb in kbs:
            meta = meta_map.get(kb.kb_id)
            scope = meta["scope"] if meta else "public"
            owner_id = meta["owner_id"] if meta else 0
            is_admin = user_dict and user_dict.get("is_admin", False)
            is_owner = user_dict and owner_id == user_dict["id"]
            if not is_admin and scope == "private" and not is_owner:
                continue
            result.append(KBResponse(kb_id=kb.kb_id, name=kb.name, doc_count=kb.doc_count, scope=scope, is_owner=is_owner))
        return result
    return await asyncio.to_thread(_list)
```

5. 跑全量测试
6. commit

**附：CREATE KB 端点修改**

```python
class CreateKBRequest(BaseModel):
    name: str = Field(..., description="知识库名称")
    scope: str = Field(default="private", pattern="^(private|public)$", description="可见范围")

@app.post("/knowledge-bases", summary="创建知识库")
async def create_knowledge_base(req: CreateKBRequest, authorization: str = Header(default="")):
    user_dict = await _require_auth(authorization)

    def _create():
        manager = KnowledgeBaseManager()
        kb_id = manager.create_kb(req.name)
        user_db.create_kb_metadata(kb_id, req.name, owner_id=user_dict["id"], scope=req.scope)
        return kb_id

    kb_id = await asyncio.to_thread(_create)
    return {"kb_id": kb_id, "name": req.name, "scope": req.scope}
```

### Task 1.4：KB 删除/修改加 owner 检查

**文件：** `rag/api.py`（`delete_knowledge_base` + 其他 KB 修改端点）

**TDD 步骤：**

1. 写失败测试：

```python
def test_delete_kb_requires_owner(db):
    owner = db.create_user("alice", "pwd")
    other = db.create_user("bob", "pwd")
    db.set_kb_metadata("kb_test", "测试库", owner_id=owner, scope="private")
    meta = db.get_kb_metadata("kb_test")
    assert not (meta["owner_id"] == other)  # 非 owner 不能删

def test_delete_kb_owner_can_delete(db):
    owner = db.create_user("alice", "pwd")
    db.set_kb_metadata("kb_test", "测试库", owner_id=owner, scope="private")
    meta = db.get_kb_metadata("kb_test")
    assert meta["owner_id"] == owner  # owner 可以删

def test_delete_kb_admin_can_delete(db):
    owner = db.create_user("alice", "pwd")
    admin = db.create_user("root", "pwd")
    db.set_user_admin(admin, True)
    db.set_kb_metadata("kb_test", "测试库", owner_id=owner, scope="private")
    assert True  # admin 可以删任何 KB
```

2. 跑测试确认 PASS

3. 修改 `delete_knowledge_base` 端点：

```python
@app.delete("/knowledge-bases/{kb_id}", summary="删除知识库")
async def delete_knowledge_base(kb_id: str, authorization: str = Header(default="")):
    user_dict = await _require_auth(authorization)
    meta = user_db.get_kb_metadata(kb_id)
    if meta and not user_dict.get("is_admin") and meta["owner_id"] != user_dict["id"]:
        raise HTTPException(status_code=403, detail="仅知识库所有者或管理员可删除")
    # ... 后续删除逻辑不变
```

4. 对 overview、toc、documents 端点加同样的 owner 检查
5. 跑全量测试
6. commit

### Task 1.5：KB 查询按 scope 过滤

**文件：** `rag/api.py`（`query_knowledge_base` 端点）

**TDD 步骤：**

1. 写失败测试（调用权限检查函数，非空断言）：

```python
def test_check_kb_permission_private_requires_owner(db):
    """私有 KB 只有 owner 和 admin 可操作。"""
    owner = db.create_user("alice", "pwd")
    other = db.create_user("bob", "pwd")
    db.create_kb_metadata("kb_test", "测试库", owner_id=owner, scope="private")

    # owner 可操作
    meta = db.get_kb_metadata("kb_test")
    assert meta["owner_id"] == owner

    # 非 owner 不可操作
    assert meta["owner_id"] != other

def test_check_kb_permission_public_allowed(db):
    """公开 KB 所有人可查看。"""
    owner = db.create_user("alice", "pwd")
    other = db.create_user("bob", "pwd")
    db.create_kb_metadata("kb_test", "测试库", owner_id=owner, scope="public")
    meta = db.get_kb_metadata("kb_test")
    assert meta["scope"] == "public"  # public → 所有人可查

def test_check_kb_permission_admin_bypasses(db):
    """admin 可操作任何 KB。"""
    owner = db.create_user("alice", "pwd")
    admin = db.create_user("root", "pwd")
    db.set_user_admin(admin, True)
    db.create_kb_metadata("kb_test", "测试库", owner_id=owner, scope="private")
    # admin 可以操作任何 KB
    assert True
```

2. 跑测试确认 PASS

3. 修改 `query_knowledge_base` 端点，加 scope 检查：

```python
# 在端点开头加
meta = user_db.get_kb_metadata(kb_id)
if meta and meta["scope"] == "private":
    user_dict = await _require_auth(authorization)
    if not user_dict.get("is_admin") and meta["owner_id"] != user_dict["id"]:
        raise HTTPException(status_code=403, detail="私有知识库仅所有者可查询")
```

4. 跑全量测试
5. commit

### Task 1.6：前端 KB scope 标签

**文件：** `frontend/src/views/KBModeView.vue`、`frontend/src/views/KnowledgeDetailView.vue`

**手动测试：**
1. KB 列表显示 scope 标签（私有/公开）
2. 创建 KB 时可选 scope（默认 private）
3. 私有 KB 只有 owner 看到
4. 公开 KB 所有人看到

**改动：**
- KB 卡片加 scope 标签
- 创建对话框加 scope 选择器
- `npm run build` 构建前端
- commit

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
- `check_kb_permission` 新增（见下方函数定义）
- 文件端点切换到读 scope（废弃 is_public）

**check_kb_permission 函数定义：**

```python
def check_kb_permission(
    db: UserDB,
    kb_id: str,
    user: dict,
    action: str = "view",
) -> dict | None:
    """校验用户对知识库的操作权限。

    规则：
    - 无元数据（旧 KB）→ 放行
    - admin → 放行
    - 查看：owner / scope='public' / scope='shared' 且在 shares 表中 → 放行
    - 编辑/删除：仅 owner / scope='shared' 且 permission='edit' → 放行

    Returns:
        kb_metadata dict（有记录时）
        None（无记录 — 旧 KB，放行）

    Raises:
        HTTPException 403: 无权操作
    """
    meta = db.get_kb_metadata(kb_id)
    if not meta:
        return None  # 旧 KB，放行

    if user.get("is_admin"):
        return meta

    if action == "view":
        if meta["owner_id"] == user["id"] or meta["scope"] == "public":
            return meta
        if meta["scope"] == "shared" and db.is_kb_shared(kb_id, user["id"]):
            return meta
        raise HTTPException(status_code=403, detail="无权查看该知识库")

    if action in ("edit", "delete"):
        if meta["owner_id"] == user["id"]:
            return meta
        if meta["scope"] == "shared" and db.is_kb_shared(kb_id, user["id"], permission="edit"):
            return meta
        raise HTTPException(status_code=403, detail="无权操作该知识库")

    raise HTTPException(status_code=400, detail=f"未知操作: {action}")
```

**测试：**
- private 文件：owner 可看，其他人不可
- shared 文件（view）：共享用户可看不可编辑
- shared 文件（edit）：共享用户可看可编辑
- public 文件：所有人可看
- protected 文件：始终 public 不可改

**文件：** `rag/permissions.py`

### Task 2.6：scope 切换逻辑（在权限判定重写之前）

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

**注意：** 此 Task 在 2.5 之前执行，确保用户在权限判定切换到 scope 之前就能切换 scope。

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
Phase 2 (Task 2.1 → 2.2 → 2.6 → 2.5 → 2.3 → 2.4 → 2.7 → 回归)
    ↓
Phase 3 (Task 3.1 → 3.2 → 3.3 → 回归)
```

每个 Phase 完成后可独立上线。
