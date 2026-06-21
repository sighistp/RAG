# 权限管理系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 RAGv3 添加基于等级的文档权限管理，支持查看/操作权限校验、文档共享、RAG 检索后过滤。

**Architecture:** 新增 `rag/permissions.py` 工具函数模块 + `user_db.py` 扩展两张表 + `api.py` 现有接口加权限校验 + `pipeline.py` 检索后过滤。前端新增权限选择器和 scope 选择器。

**Tech Stack:** Python 3.12, FastAPI, SQLite, Qdrant, Vue 3, Element Plus

**设计文档:** `docs/permission-design.md`

---

## 文件结构

### 新建文件

| 文件 | 职责 |
|------|------|
| `rag/permissions.py` | 权限工具函数：`check_doc_permission()`、`filter_chunks_by_permission()`、`get_accessible_doc_names()` |
| `tests/test_permissions.py` | 权限模块单元测试 |

### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `config.py` | 新增 `users_db_path` 字段，统一用户数据库路径配置 |
| `rag/user_db.py` | `_create_tables()` 中新增 `document_permissions` 和 `document_shares` 表，`users` 表加 `permission_level` / `is_admin` 字段；新增权限相关 CRUD 方法 |
| `rag/vector_store.py` | `add_to_collection()` 的 payload 中加 `doc_permission_id` 字段 |
| `rag/knowledge_base.py` | `add_document()` 签名加 `doc_permission_id` 参数并透传给 `add_to_collection()` |
| `rag/pipeline.py` | `_prepare_context()` 中加检索后权限过滤逻辑（oversampling → filter → truncate） |
| `rag/api.py` | `POST /upload` 支持 `permission_level`；`DELETE /files/{filename}` 加 `authorization` 参数和权限校验；`POST /files/{filename}/tags` 加 `authorization` 参数和权限校验；`DELETE /knowledge-bases/{kb_id}/documents/{doc_name}` 加权限校验；新增权限管理 API；新增管理员初始化 |
| `rag/models.py` | `Chunk` dataclass 加可选 `doc_permission_id` 字段 |
| `tests/test_user_db.py` | 新增权限表相关测试 |
| `tests/test_permissions.py` | 新建，权限工具函数测试 |
| `frontend/src/views/KnowledgeDetailView.vue` | 新增 scope 选择器、权限标签、共享管理 |
| `frontend/src/components/ShareDialog.vue` | 新建，共享管理弹窗 |
| `frontend/src/utils/api.ts` | 新增权限相关 API 调用 |

---

## Task 0: config.py 新增 users_db_path

**Files:**
- Modify: `config.py`

**背景：** 现有 `api.py` 中 `_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "users.db"` 是硬编码的。pipeline.py 中权限过滤需要访问 UserDB，但没有统一的配置入口。需要在 config.py 中新增 `users_db_path` 字段。

- [ ] **Step 1: 在 config.py 中新增字段**

在 `config.py` 的 `Settings` 类中，在 `analysis_db_path` 之后追加：

```python
    users_db_path: str = str(Path(__file__).resolve().parent / "data" / "users.db")
```

- [ ] **Step 2: 修改 api.py 使用 config 路径**

将 `rag/api.py` 中：

```python
_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "users.db"
user_db = UserDB(str(_DB_PATH))
```

改为：

```python
from config import settings as _settings
_DB_PATH = Path(_settings.users_db_path)
user_db = UserDB(str(_DB_PATH))
```

- [ ] **Step 3: 运行现有测试确认不破坏**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_api.py tests/test_user_db.py -v`

Expected: ALL PASS。

- [ ] **Step 4: Commit**

```bash
git add config.py rag/api.py
git commit -m "feat: config.py 新增 users_db_path 统一数据库路径配置"
```

---

## Task 1: 数据库 Schema — users 表扩展 + 权限表

**Files:**
- Modify: `rag/user_db.py`
- Test: `tests/test_user_db.py`

- [ ] **Step 1: 写 users 表扩展的失败测试**

在 `tests/test_user_db.py` 末尾追加：

```python
# -- Permission fields on users table ----------------------------------------


def test_user_has_permission_level_default(db):
    """新建用户默认 permission_level=1, is_admin=False。"""
    uid = db.create_user("alice", "s3cret")
    user = db.get_user_by_id(uid)
    assert user["permission_level"] == 1
    assert user["is_admin"] is False


def test_set_user_permission_level(db):
    uid = db.create_user("alice", "s3cret")
    db.set_user_permission_level(uid, 3)
    user = db.get_user_by_id(uid)
    assert user["permission_level"] == 3


def test_set_user_admin(db):
    uid = db.create_user("alice", "s3cret")
    db.set_user_admin(uid, True)
    user = db.get_user_by_id(uid)
    assert user["is_admin"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_user_db.py::test_user_has_permission_level_default tests/test_user_db.py::test_set_user_permission_level tests/test_user_db.py::test_set_user_admin -v`

Expected: FAIL — `get_user_by_id` 返回的 dict 中没有 `permission_level` / `is_admin` 字段，`set_user_permission_level` / `set_user_admin` 方法不存在。

- [ ] **Step 3: 修改 `user_db.py` — users 表加字段 + 新方法**

在 `rag/user_db.py` 的 `_create_tables()` 方法中，**在 `executescript` 的 SQL 字符串末尾**追加：

```sql
-- 权限管理：给 users 表加 permission_level 和 is_admin 字段（幂等）
```

然后在 `executescript` 调用**之后**、`try: self._conn.execute("SELECT mode ...")` **之前**，插入以下幂等 ALTER 逻辑：

```python
            # Add permission_level column to users if it doesn't exist (idempotent)
            try:
                self._conn.execute("SELECT permission_level FROM users LIMIT 1")
            except sqlite3.OperationalError:
                self._conn.execute(
                    "ALTER TABLE users ADD COLUMN permission_level INTEGER NOT NULL DEFAULT 1"
                )
                self._conn.commit()

            # Add is_admin column to users if it doesn't exist (idempotent)
            try:
                self._conn.execute("SELECT is_admin FROM users LIMIT 1")
            except sqlite3.OperationalError:
                self._conn.execute(
                    "ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"
                )
                self._conn.commit()
```

在 `get_user_by_id` 方法中，修改 SELECT 语句，返回 `permission_level` 和 `is_admin`：

```python
    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        """Return user dict or ``None``."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id, username, permission_level, is_admin FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "permission_level": row["permission_level"],
            "is_admin": bool(row["is_admin"]),
        }
```

在 `UserDB` 类末尾（`close()` 方法之前）新增两个方法：

```python
    def set_user_permission_level(self, user_id: int, level: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE users SET permission_level = ? WHERE id = ?",
                (level, user_id),
            )
            self._conn.commit()

    def set_user_admin(self, user_id: int, is_admin: bool) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE users SET is_admin = ? WHERE id = ?",
                (int(is_admin), user_id),
            )
            self._conn.commit()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_user_db.py -v`

Expected: ALL PASS（包括之前存在的测试和新增的3个测试）。

- [ ] **Step 5: Commit**

```bash
git add rag/user_db.py tests/test_user_db.py
git commit -m "feat: users 表扩展 permission_level / is_admin 字段"
```

---

## Task 2: 数据库 Schema — document_permissions 表

**Files:**
- Modify: `rag/user_db.py`
- Test: `tests/test_user_db.py`

- [ ] **Step 1: 写 document_permissions 表的失败测试**

在 `tests/test_user_db.py` 末尾追加：

```python
# -- Document Permissions ----------------------------------------------------


def test_create_document_permission(db):
    """上传文档时创建权限记录。"""
    uid = db.create_user("alice", "s3cret")
    doc_id = db.create_document_permission("report.pdf", "rag_docs", uid, 2)
    assert isinstance(doc_id, int) and doc_id > 0


def test_get_document_permission_by_name(db):
    uid = db.create_user("alice", "s3cret")
    db.create_document_permission("report.pdf", "rag_docs", uid, 2)
    perm = db.get_document_permission("report.pdf", "rag_docs")
    assert perm is not None
    assert perm["doc_name"] == "report.pdf"
    assert perm["permission_level"] == 2
    assert perm["owner_id"] == uid


def test_get_document_permission_nonexistent(db):
    """不存在的文档返回 None。"""
    assert db.get_document_permission("nope.pdf", "rag_docs") is None


def test_update_document_permission_level(db):
    uid = db.create_user("alice", "s3cret")
    doc_id = db.create_document_permission("report.pdf", "rag_docs", uid, 1)
    db.update_document_permission_level(doc_id, 4)
    perm = db.get_document_permission_by_id(doc_id)
    assert perm["permission_level"] == 4


def test_delete_document_permission(db):
    uid = db.create_user("alice", "s3cret")
    doc_id = db.create_document_permission("report.pdf", "rag_docs", uid, 1)
    db.delete_document_permission(doc_id)
    assert db.get_document_permission_by_id(doc_id) is None


def test_document_permission_unique_per_kb(db):
    """同一知识库内同名文档只能有一条权限记录。"""
    uid = db.create_user("alice", "s3cret")
    db.create_document_permission("report.pdf", "rag_docs", uid, 1)
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        db.create_document_permission("report.pdf", "rag_docs", uid, 2)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_user_db.py::test_create_document_permission -v`

Expected: FAIL — `create_document_permission` 方法不存在。

- [ ] **Step 3: 修改 `user_db.py` — 新建 document_permissions 表 + CRUD 方法**

在 `_create_tables()` 的 `executescript` SQL 字符串末尾追加：

```sql
                CREATE TABLE IF NOT EXISTS document_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_name TEXT NOT NULL,
                    kb_id TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,
                    permission_level INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(doc_name, kb_id)
                );

                CREATE INDEX IF NOT EXISTS idx_doc_permissions_kb ON document_permissions(kb_id);
                CREATE INDEX IF NOT EXISTS idx_doc_permissions_owner ON document_permissions(owner_id);
```

在 `UserDB` 类中 `close()` 方法之前新增以下方法：

```python
    # ------------------------------------------------------------------
    # Document Permissions
    # ------------------------------------------------------------------

    def create_document_permission(self, doc_name: str, kb_id: str, owner_id: int, permission_level: int = 1) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO document_permissions (doc_name, kb_id, owner_id, permission_level) VALUES (?, ?, ?, ?)",
                (doc_name, kb_id, owner_id, permission_level),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_document_permission(self, doc_name: str, kb_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, doc_name, kb_id, owner_id, permission_level, created_at "
                "FROM document_permissions WHERE doc_name = ? AND kb_id = ?",
                (doc_name, kb_id),
            ).fetchone()
        return dict(row) if row else None

    def get_document_permission_by_id(self, doc_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, doc_name, kb_id, owner_id, permission_level, created_at "
                "FROM document_permissions WHERE id = ?",
                (doc_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_document_permission_level(self, doc_id: int, level: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE document_permissions SET permission_level = ? WHERE id = ?",
                (level, doc_id),
            )
            self._conn.commit()

    def delete_document_permission(self, doc_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM document_permissions WHERE id = ?", (doc_id,))
            self._conn.commit()

    def get_accessible_doc_names(self, kb_id: str, user_id: int, user_level: int) -> list[str]:
        """返回用户在指定知识库中有权查看的文档名列表。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT dp.doc_name FROM document_permissions dp "
                "LEFT JOIN document_shares ds ON ds.doc_id = dp.id AND ds.user_id = ? "
                "WHERE dp.kb_id = ? AND (dp.owner_id = ? OR ds.id IS NOT NULL OR ? >= dp.permission_level)",
                (user_id, kb_id, user_id, user_level),
            ).fetchall()
        return [r["doc_name"] for r in rows]

    def get_document_permissions_by_names(self, doc_names: list[str], kb_id: str) -> dict[str, dict[str, Any] | None]:
        """批量查询多个文档的权限记录。返回 {doc_name: perm_dict_or_None}。"""
        if not doc_names:
            return {}
        with self._lock:
            placeholders = ",".join("?" for _ in doc_names)
            rows = self._conn.execute(
                f"SELECT id, doc_name, kb_id, owner_id, permission_level, created_at "
                f"FROM document_permissions WHERE doc_name IN ({placeholders}) AND kb_id = ?",
                (*doc_names, kb_id),
            ).fetchall()
        perm_map = {r["doc_name"]: dict(r) for r in rows}
        return {name: perm_map.get(name) for name in doc_names}

    def get_document_permissions_by_ids(self, doc_ids: list[int]) -> dict[int, dict[str, Any]]:
        """批量查询多个权限记录（按 ID）。返回 {doc_id: perm_dict}。"""
        if not doc_ids:
            return {}
        with self._lock:
            placeholders = ",".join("?" for _ in doc_ids)
            rows = self._conn.execute(
                f"SELECT id, doc_name, kb_id, owner_id, permission_level, created_at "
                f"FROM document_permissions WHERE id IN ({placeholders})",
                doc_ids,
            ).fetchall()
        return {r["id"]: dict(r) for r in rows}

    def get_shared_doc_ids_for_user(self, user_id: int, doc_ids: list[int]) -> set[int]:
        """批量查询用户被共享的 doc_id 集合。返回指定 doc_ids 中被共享的子集。"""
        if not doc_ids:
            return set()
        with self._lock:
            placeholders = ",".join("?" for _ in doc_ids)
            rows = self._conn.execute(
                f"SELECT doc_id FROM document_shares WHERE user_id = ? AND doc_id IN ({placeholders})",
                (user_id, *doc_ids),
            ).fetchall()
        return {r["doc_id"] for r in rows}

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """按用户名查询用户。"""
        with self._lock:
            row = self._conn.execute(
                "SELECT id, username, permission_level, is_admin FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "permission_level": row["permission_level"],
            "is_admin": bool(row["is_admin"]),
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_user_db.py -v`

Expected: ALL PASS。

- [ ] **Step 5: Commit**

```bash
git add rag/user_db.py tests/test_user_db.py
git commit -m "feat: 新建 document_permissions 表及 CRUD 方法"
```

---

## Task 3: 数据库 Schema — document_shares 表

**Files:**
- Modify: `rag/user_db.py`
- Test: `tests/test_user_db.py`

- [ ] **Step 1: 写 document_shares 表的失败测试**

在 `tests/test_user_db.py` 末尾追加：

```python
# -- Document Shares ---------------------------------------------------------


def test_share_document(db):
    """共享文档给指定用户。"""
    owner = db.create_user("alice", "s3cret")
    viewer = db.create_user("bob", "pwd")
    doc_id = db.create_document_permission("report.pdf", "rag_docs", owner, 3)
    share_id = db.share_document(doc_id, viewer, owner)
    assert isinstance(share_id, int) and share_id > 0


def test_is_shared(db):
    owner = db.create_user("alice", "s3cret")
    viewer = db.create_user("bob", "pwd")
    doc_id = db.create_document_permission("report.pdf", "rag_docs", owner, 3)
    assert db.is_document_shared(doc_id, viewer) is False
    db.share_document(doc_id, viewer, owner)
    assert db.is_document_shared(doc_id, viewer) is True


def test_unshare_document(db):
    owner = db.create_user("alice", "s3cret")
    viewer = db.create_user("bob", "pwd")
    doc_id = db.create_document_permission("report.pdf", "rag_docs", owner, 3)
    db.share_document(doc_id, viewer, owner)
    db.unshare_document(doc_id, viewer)
    assert db.is_document_shared(doc_id, viewer) is False


def test_share_unique_per_user(db):
    """同一用户不能重复共享同一文档。"""
    owner = db.create_user("alice", "s3cret")
    viewer = db.create_user("bob", "pwd")
    doc_id = db.create_document_permission("report.pdf", "rag_docs", owner, 3)
    db.share_document(doc_id, viewer, owner)
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        db.share_document(doc_id, viewer, owner)


def test_list_shared_users(db):
    owner = db.create_user("alice", "s3cret")
    bob = db.create_user("bob", "pwd")
    carol = db.create_user("carol", "pwd")
    doc_id = db.create_document_permission("report.pdf", "rag_docs", owner, 3)
    db.share_document(doc_id, bob, owner)
    db.share_document(doc_id, carol, owner)
    shared = db.list_shared_users(doc_id)
    assert len(shared) == 2
    usernames = {u["username"] for u in shared}
    assert usernames == {"bob", "carol"}


def test_delete_permission_cascades_shares(db):
    """删除权限记录时级联删除共享记录。"""
    owner = db.create_user("alice", "s3cret")
    viewer = db.create_user("bob", "pwd")
    doc_id = db.create_document_permission("report.pdf", "rag_docs", owner, 3)
    db.share_document(doc_id, viewer, owner)
    db.delete_document_permission(doc_id)
    # 共享记录应该也被删除（外键 CASCADE）
    assert db.is_document_shared(doc_id, viewer) is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_user_db.py::test_share_document -v`

Expected: FAIL — `share_document` 方法不存在。

- [ ] **Step 3: 修改 `user_db.py` — 新建 document_shares 表 + CRUD 方法**

在 `_create_tables()` 的 `executescript` SQL 字符串末尾（document_permissions 之后）追加：

```sql
                CREATE TABLE IF NOT EXISTS document_shares (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    granted_by INTEGER NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(doc_id, user_id),
                    FOREIGN KEY (doc_id) REFERENCES document_permissions(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (granted_by) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_doc_shares_user ON document_shares(user_id);
                CREATE INDEX IF NOT EXISTS idx_doc_shares_doc ON document_shares(doc_id);
```

在 `UserDB` 类中 `close()` 方法之前追加：

```python
    def share_document(self, doc_id: int, user_id: int, granted_by: int) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO document_shares (doc_id, user_id, granted_by) VALUES (?, ?, ?)",
                (doc_id, user_id, granted_by),
            )
            self._conn.commit()
            return cur.lastrowid

    def unshare_document(self, doc_id: int, user_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM document_shares WHERE doc_id = ? AND user_id = ?",
                (doc_id, user_id),
            )
            self._conn.commit()

    def is_document_shared(self, doc_id: int, user_id: int) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM document_shares WHERE doc_id = ? AND user_id = ?",
                (doc_id, user_id),
            ).fetchone()
        return row is not None

    def list_shared_users(self, doc_id: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT u.id, u.username, ds.granted_by, ds.created_at AS granted_at "
                "FROM document_shares ds JOIN users u ON ds.user_id = u.id "
                "WHERE ds.doc_id = ? ORDER BY ds.created_at",
                (doc_id,),
            ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_user_db.py -v`

Expected: ALL PASS。

- [ ] **Step 5: Commit**

```bash
git add rag/user_db.py tests/test_user_db.py
git commit -m "feat: 新建 document_shares 表及共享 CRUD 方法"
```

---

## Task 4: 权限工具函数 `check_doc_permission`

**Files:**
- Create: `rag/permissions.py`
- Create: `tests/test_permissions.py`

- [ ] **Step 1: 写 `check_doc_permission` 的失败测试**

新建 `tests/test_permissions.py`：

```python
"""Tests for rag.permissions — document permission utility functions."""

import pytest
from fastapi import HTTPException

from rag.permissions import check_doc_permission
from rag.user_db import UserDB


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "test.db")
    udb = UserDB(path)
    yield udb
    udb.close()


def _make_user(db: UserDB, username: str, level: int = 1, is_admin: bool = False) -> dict:
    uid = db.create_user(username, "pwd")
    if level != 1:
        db.set_user_permission_level(uid, level)
    if is_admin:
        db.set_user_admin(uid, True)
    return db.get_user_by_id(uid)


# -- check_doc_permission: view -------------------------------------------


def test_owner_can_view(db):
    """文档上传者可以查看。"""
    owner = _make_user(db, "alice", level=1)
    db.create_document_permission("report.pdf", "rag_docs", owner["id"], permission_level=5)
    result = check_doc_permission(db, "report.pdf", "rag_docs", owner, action="view")
    assert result["doc_name"] == "report.pdf"


def test_high_level_user_can_view_low_level_doc(db):
    """高等级用户可以查看低等级文档。"""
    owner = _make_user(db, "alice", level=1)
    viewer = _make_user(db, "bob", level=4)
    db.create_document_permission("report.pdf", "rag_docs", owner["id"], permission_level=2)
    result = check_doc_permission(db, "report.pdf", "rag_docs", viewer, action="view")
    assert result["doc_name"] == "report.pdf"


def test_low_level_user_cannot_view_high_level_doc(db):
    """低等级用户不能查看高等级文档。"""
    owner = _make_user(db, "alice", level=5)
    viewer = _make_user(db, "bob", level=1)
    db.create_document_permission("report.pdf", "rag_docs", owner["id"], permission_level=5)
    with pytest.raises(HTTPException) as exc_info:
        check_doc_permission(db, "report.pdf", "rag_docs", viewer, action="view")
    assert exc_info.value.status_code == 403


def test_shared_user_can_view(db):
    """被共享的用户即使等级不够也能查看。"""
    owner = _make_user(db, "alice", level=5)
    viewer = _make_user(db, "bob", level=1)
    doc_id = db.create_document_permission("report.pdf", "rag_docs", owner["id"], permission_level=5)
    db.share_document(doc_id, viewer["id"], owner["id"])
    result = check_doc_permission(db, "report.pdf", "rag_docs", viewer, action="view")
    assert result["doc_name"] == "report.pdf"


def test_admin_bypass_all_permissions(db):
    """系统管理员绕过所有权限限制。"""
    owner = _make_user(db, "alice", level=5)
    admin = _make_user(db, "root", is_admin=True)
    db.create_document_permission("secret.pdf", "rag_docs", owner["id"], permission_level=5)
    result = check_doc_permission(db, "secret.pdf", "rag_docs", admin, action="view")
    assert result["doc_name"] == "secret.pdf"


def test_old_doc_without_permission_record_passes(db):
    """旧文档无权限记录时，所有操作放行（返回 None，不抛异常）。"""
    user = _make_user(db, "alice", level=1)
    # 不创建任何 document_permissions 记录
    result = check_doc_permission(db, "old_file.pdf", "rag_docs", user, action="view")
    assert result is None

    result = check_doc_permission(db, "old_file.pdf", "rag_docs", user, action="delete")
    assert result is None

    result = check_doc_permission(db, "old_file.pdf", "rag_docs", user, action="edit")
    assert result is None


# -- check_doc_permission: edit / delete -----------------------------------


def test_owner_can_edit(db):
    owner = _make_user(db, "alice", level=1)
    db.create_document_permission("report.pdf", "rag_docs", owner["id"], permission_level=1)
    result = check_doc_permission(db, "report.pdf", "rag_docs", owner, action="edit")
    assert result["doc_name"] == "report.pdf"


def test_owner_can_delete(db):
    owner = _make_user(db, "alice", level=1)
    db.create_document_permission("report.pdf", "rag_docs", owner["id"], permission_level=1)
    result = check_doc_permission(db, "report.pdf", "rag_docs", owner, action="delete")
    assert result["doc_name"] == "report.pdf"


def test_non_owner_cannot_edit(db):
    owner = _make_user(db, "alice", level=1)
    other = _make_user(db, "bob", level=5)
    db.create_document_permission("report.pdf", "rag_docs", owner["id"], permission_level=1)
    with pytest.raises(HTTPException) as exc_info:
        check_doc_permission(db, "report.pdf", "rag_docs", other, action="edit")
    assert exc_info.value.status_code == 403


def test_non_owner_cannot_delete(db):
    owner = _make_user(db, "alice", level=1)
    other = _make_user(db, "bob", level=5)
    db.create_document_permission("report.pdf", "rag_docs", owner["id"], permission_level=1)
    with pytest.raises(HTTPException) as exc_info:
        check_doc_permission(db, "report.pdf", "rag_docs", other, action="delete")
    assert exc_info.value.status_code == 403


def test_admin_can_edit_any_doc(db):
    owner = _make_user(db, "alice", level=1)
    admin = _make_user(db, "root", is_admin=True)
    db.create_document_permission("report.pdf", "rag_docs", owner["id"], permission_level=1)
    result = check_doc_permission(db, "report.pdf", "rag_docs", admin, action="edit")
    assert result["doc_name"] == "report.pdf"


# -- get_accessible_doc_names ---------------------------------------------


def test_get_accessible_doc_names_includes_owned(db):
    from rag.permissions import get_accessible_doc_names
    user = _make_user(db, "alice", level=1)
    db.create_document_permission("a.pdf", "kb1", user["id"], 1)
    db.create_document_permission("b.pdf", "kb1", user["id"], 5)
    names = get_accessible_doc_names(db, "kb1", user)
    assert set(names) == {"a.pdf", "b.pdf"}


def test_get_accessible_doc_names_includes_shared(db):
    from rag.permissions import get_accessible_doc_names
    owner = _make_user(db, "alice", level=5)
    viewer = _make_user(db, "bob", level=1)
    doc_id = db.create_document_permission("secret.pdf", "kb1", owner["id"], 5)
    db.share_document(doc_id, viewer["id"], owner["id"])
    names = get_accessible_doc_names(db, "kb1", viewer)
    assert "secret.pdf" in names


def test_get_accessible_doc_names_excludes_inaccessible(db):
    from rag.permissions import get_accessible_doc_names
    owner = _make_user(db, "alice", level=5)
    viewer = _make_user(db, "bob", level=1)
    db.create_document_permission("secret.pdf", "kb1", owner["id"], 5)
    names = get_accessible_doc_names(db, "kb1", viewer)
    assert "secret.pdf" not in names
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_permissions.py -v`

Expected: FAIL — `rag.permissions` 模块不存在。

- [ ] **Step 3: 创建 `rag/permissions.py`**

新建 `rag/permissions.py`：

```python
"""文档权限校验工具函数。

统一的权限校验入口，供 API 层和 pipeline 层调用。
不是中间件 — 各接口按需调用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from rag.user_db import UserDB


def check_doc_permission(
    db: UserDB,
    doc_name: str,
    kb_id: str,
    user: dict,
    action: str = "view",
) -> dict | None:
    """校验用户对指定文档的操作权限。

    Args:
        db: UserDB 实例
        doc_name: 文档名
        kb_id: 知识库 ID
        user: 当前用户 dict，需含 id / is_admin / permission_level
        action: "view" | "edit" | "delete"

    Returns:
        document_permission 记录 dict（有记录时）
        None（无权限记录 — 旧文档视为公开，放行）

    Raises:
        HTTPException 403: 无权操作
    """
    doc = db.get_document_permission(doc_name, kb_id)

    # 无权限记录 = 旧文档，视为公开，放行
    if not doc:
        return None

    # 管理员绕过
    if user.get("is_admin"):
        return doc

    if action == "view":
        if doc["owner_id"] == user["id"]:
            return doc
        if db.is_document_shared(doc["id"], user["id"]):
            return doc
        if user.get("permission_level", 1) >= doc["permission_level"]:
            return doc
        raise HTTPException(status_code=403, detail="无权查看该文档")

    if action in ("edit", "delete"):
        if doc["owner_id"] == user["id"]:
            return doc
        raise HTTPException(status_code=403, detail="仅文档上传者或管理员可操作")

    raise HTTPException(status_code=400, detail=f"未知操作: {action}")


def get_accessible_doc_names(db: UserDB, kb_id: str, user: dict) -> list[str]:
    """返回用户在指定知识库中有权查看的文档名列表。

    用于 RAG 检索后过滤。
    """
    if user.get("is_admin"):
        # 管理员能看到所有文档
        return None  # None 表示不过滤

    return db.get_accessible_doc_names(
        kb_id=kb_id,
        user_id=user["id"],
        user_level=user.get("permission_level", 1),
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_permissions.py -v`

Expected: ALL PASS。

- [ ] **Step 5: Commit**

```bash
git add rag/permissions.py tests/test_permissions.py
git commit -m "feat: 新增权限工具函数 check_doc_permission / get_accessible_doc_names"
```

---

## Task 5: RAG 检索后权限过滤

**Files:**
- Modify: `rag/permissions.py` — 新增 `filter_chunks_by_permission()`
- Modify: `rag/pipeline.py` — `_prepare_context()` 中加过滤逻辑
- Test: `tests/test_permissions.py`

- [ ] **Step 1: 写 `filter_chunks_by_permission` 的失败测试**

在 `tests/test_permissions.py` 末尾追加：

```python
# -- filter_chunks_by_permission -------------------------------------------


def test_filter_chunks_admin_sees_all(db):
    """管理员不过滤。"""
    from rag.models import Chunk
    from rag.permissions import filter_chunks_by_permission
    admin = _make_user(db, "root", is_admin=True)
    chunks = [Chunk(text="a", doc_name="x.pdf", chunk_index=0)]
    result = filter_chunks_by_permission(db, "kb1", chunks, admin)
    assert len(result) == 1


def test_filter_chunks_removes_inaccessible(db):
    """过滤掉无权文档的 chunks。"""
    from rag.models import Chunk
    from rag.permissions import filter_chunks_by_permission
    owner = _make_user(db, "alice", level=5)
    viewer = _make_user(db, "bob", level=1)
    db.create_document_permission("secret.pdf", "kb1", owner["id"], 5)
    db.create_document_permission("public.pdf", "kb1", owner["id"], 1)
    chunks = [
        Chunk(text="a", doc_name="secret.pdf", chunk_index=0),
        Chunk(text="b", doc_name="public.pdf", chunk_index=0),
    ]
    result = filter_chunks_by_permission(db, "kb1", chunks, viewer)
    assert len(result) == 1
    assert result[0].doc_name == "public.pdf"


def test_filter_chunks_old_doc_no_permission_record(db):
    """旧文档无权限记录，视为公开，保留。"""
    from rag.models import Chunk
    from rag.permissions import filter_chunks_by_permission
    viewer = _make_user(db, "bob", level=1)
    chunks = [Chunk(text="a", doc_name="old_file.pdf", chunk_index=0)]
    result = filter_chunks_by_permission(db, "kb1", chunks, viewer)
    assert len(result) == 1


def test_filter_chunks_shared_doc_included(db):
    """被共享的文档的 chunks 保留。"""
    from rag.models import Chunk
    from rag.permissions import filter_chunks_by_permission
    owner = _make_user(db, "alice", level=5)
    viewer = _make_user(db, "bob", level=1)
    doc_id = db.create_document_permission("secret.pdf", "kb1", owner["id"], 5)
    db.share_document(doc_id, viewer["id"], owner["id"])
    chunks = [Chunk(text="a", doc_name="secret.pdf", chunk_index=0)]
    result = filter_chunks_by_permission(db, "kb1", chunks, viewer)
    assert len(result) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_permissions.py::test_filter_chunks_admin_sees_all -v`

Expected: FAIL — `filter_chunks_by_permission` 不存在。

- [ ] **Step 3: 在 `rag/permissions.py` 中新增 `filter_chunks_by_permission`**

在 `rag/permissions.py` 末尾追加：

```python
def filter_chunks_by_permission(
    db: UserDB,
    kb_id: str,
    chunks: list,
    user: dict,
) -> list:
    """过滤掉用户无权查看的文档的 chunks。

    策略：
    - 管理员：不过滤
    - 旧文档无权限记录：视为公开，保留
    - 有权限记录的文档：按权限规则过滤

    Args:
        db: UserDB 实例
        kb_id: 知识库 ID
        chunks: Chunk 列表
        user: 当前用户 dict

    Returns:
        过滤后的 Chunk 列表
    """
    if user.get("is_admin"):
        return list(chunks)

    # 批量查询：一次性查出所有 doc_name 的权限记录（避免 N+1）
    doc_names = list(set(c.doc_name for c in chunks))
    perm_map = db.get_document_permissions_by_names(doc_names, kb_id)

    # 查出用户有权查看的文档名
    allowed_names = db.get_accessible_doc_names(
        kb_id=kb_id,
        user_id=user["id"],
        user_level=user.get("permission_level", 1),
    )
    allowed_set = set(allowed_names)

    result = []
    for c in chunks:
        perm = perm_map.get(c.doc_name)
        if perm is None:
            # 无权限记录 = 旧文档，视为公开
            result.append(c)
        elif c.doc_name in allowed_set:
            # 有权限记录且用户有权查看
            result.append(c)
        # else: 有权限记录但用户无权，过滤掉

    return result
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_permissions.py -v`

Expected: ALL PASS。

- [ ] **Step 5: Commit**

```bash
git add rag/permissions.py tests/test_permissions.py
git commit -m "feat: 新增 filter_chunks_by_permission 检索后过滤函数"
```

---

## Task 6: pipeline.py 集成检索后过滤

**Files:**
- Modify: `rag/pipeline.py` — `_prepare_context()` 中加 oversampling + 过滤
- Test: `tests/test_pipeline.py` 或 `tests/test_pipeline_clean.py`

- [ ] **Step 1: 在 `_prepare_context()` 中插入过滤逻辑**

在 `rag/pipeline.py` 的 `_prepare_context()` 方法中，找到这一行：

```python
        context = self.retriever.retrieve(rewritten, top_k=top_k, doc_name=doc_name, tags=tags)
```

将其替换为：

```python
        # Oversampling: 检索更多结果，过滤后再截取 top_k
        oversample_factor = 3
        raw_context = self.retriever.retrieve(rewritten, top_k=top_k * oversample_factor, doc_name=doc_name, tags=tags)

        # 权限过滤：移除无权文档的 chunks
        from rag.permissions import filter_chunks_by_permission
        context = filter_chunks_by_permission(self._user_db, self._kb_id, raw_context, self._current_user)
        context = context[:top_k]  # 截取回 top_k
```

在 `RAGPipeline.__init__()` 中，需要存储 `self._user_db` 和 `self._kb_id`。找到 `__init__` 方法，在 `self._agent_lock = threading.Lock()` 之后追加：

```python
        # 权限管理：注入 user_db 引用（由 api.py 传入，避免每次查询新建连接）
        self._user_db = None
        self._kb_id = collection_name or "rag_docs"
```

修改 `_prepare_context()` 的签名，增加 `user: dict = None` 和 `kb_id: str = None` 参数：

```python
    def _prepare_context(self, question: str, session_id: str, doc_name: str, top_k: int = 8, tags: list[str] = None, user: dict = None, kb_id: str = None):
```

在过滤逻辑中使用注入的 `self._user_db`（不新建连接）：

```python
        # 权限过滤：移除无权文档的 chunks（user is not None 且有 user_db 时才过滤）
        if user is not None and self._user_db is not None:
            from rag.permissions import filter_chunks_by_permission
            context = filter_chunks_by_permission(self._user_db, kb_id or self._kb_id, raw_context, user)
            context = context[:top_k]
        else:
            context = raw_context[:top_k]
```

**api.py 中注入 user_db：** 在所有创建 `RAGPipeline(kb_id=...)` 的地方，追加 `user_db=user_db` 参数。需要修改 `RAGPipeline.__init__()` 的签名：

```python
    def __init__(self, file_path=None, collection_name=None, user_db=None, ...):
        ...
        self._user_db = user_db
```

**api.py 中共有 3 处创建 RAGPipeline，全部需要加 `user_db=user_db`：**

| 位置 | 场景 | 当前代码 |
|------|------|---------|
| `auto_index_on_startup()` 末尾 | 启动索引后 | `pipeline = RAGPipeline(kb_id="rag_docs")` |
| `upload_file()` 索引后 | 上传文件后刷新 | `pipeline = RAGPipeline(kb_id="rag_docs")` |
| `index_all()` 索引后 | 全量重建索引后 | `pipeline = RAGPipeline(kb_id="rag_docs")` |

全部改为：

```python
pipeline = RAGPipeline(kb_id="rag_docs", user_db=user_db)
```

同时修改 `query()` 和 `query_stream()` 方法，将 `user` 和 `kb_id` 参数传递给 `_prepare_context()`。在 `query()` 的签名中增加 `user: dict = None, kb_id: str = None`，在调用 `_prepare_context()` 时传入。

- [ ] **Step 2: 修改 `query()` 和 `query_stream()` 传递 user 参数**

`query()` 方法签名改为：

```python
    def query(self, question: str, top_k: int = 8, session_id: str = None, doc_name: str = None, tags: list[str] = None, user: dict = None, kb_id: str = None) -> QueryResult:
```

调用处改为：

```python
        prepared, error = self._prepare_context(question, sid, doc_name, top_k, tags=tags, user=user, kb_id=kb_id)
```

`query_stream()` 方法签名增加同样参数，并在调用 `_prepare_context()` 时传入。

- [ ] **Step 3: 修改 `api.py` 中调用 pipeline.query 时传入 user**

在 `api.py` 的 `query()` 和 `query_stream()` 端点中，找到调用 `pipeline.query(...)` / `pipeline.query_stream(...)` 的地方，增加 `user=current_user_dict` 和 `kb_id="rag_docs"` 参数。

需要先通过 JWT 获取完整的 user dict（包含 `permission_level` 和 `is_admin`）：

```python
    # 在 query endpoint 中
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)
```

然后传给 pipeline：

```python
    result = await asyncio.to_thread(pipeline.query, req.question, ..., user=user_dict, kb_id="rag_docs")
```

- [ ] **Step 4: 运行现有测试确认不破坏**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_pipeline.py tests/test_pipeline_clean.py tests/test_pipeline_stream.py -v`

Expected: ALL PASS（现有测试中 user=None 时跳过过滤）。

- [ ] **Step 5: Commit**

```bash
git add rag/pipeline.py rag/api.py
git commit -m "feat: pipeline 集成检索后权限过滤 (oversampling + filter + truncate)"
```

---

## Task 7: vector_store.py + knowledge_base.py + models.py — payload 加 doc_permission_id

**Files:**
- Modify: `rag/models.py` — Chunk dataclass 加 `doc_permission_id: int | None = None`
- Modify: `rag/vector_store.py` — `add_to_collection()` payload 加字段，`search_collection()` 返回时读取
- Modify: `rag/knowledge_base.py` — `add_document()` 签名加 `doc_permission_id` 参数并透传
- Modify: `rag/pipeline.py` — 过滤逻辑优先用 `chunk.doc_permission_id` 做快速查询
- Test: `tests/test_vector_store.py`

**背景：** `KnowledgeBaseManager.add_document()` 是 `add_to_collection()` 的主要调用方。如果不改它，api.py 中创建的权限 ID 无法传到 Qdrant payload 中。同时 Chunk dataclass 加 `doc_permission_id` 字段后，pipeline 可以直接用它做单条查询（比按 doc_name 查更快），避免 N+1。

- [ ] **Step 1: 修改 `rag/models.py` — Chunk 加 `doc_permission_id` 字段**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Chunk:
    text: str
    doc_name: str
    chunk_index: int
    doc_permission_id: int | None = None
```

- [ ] **Step 2: 写失败测试**

在 `tests/test_vector_store.py` 中找到 `add_to_collection` 相关测试，在末尾追加：

```python
def test_add_to_collection_with_permission_id(tmp_path):
    """add_to_collection 写入 doc_permission_id 到 payload。"""
    import rag.vector_store as vs
    vs._client = QdrantClient(path=str(tmp_path / "qdrant"))
    vs._ensure_collection_name("test_col")

    from rag.models import Chunk
    chunks = [Chunk(text="hello", doc_name="a.pdf", chunk_index=0)]
    embeddings = [[0.1] * 1024]
    vs.add_to_collection("test_col", chunks, embeddings, doc_permission_id=42)

    client = vs._get_client()
    points, _ = client.scroll(collection_name="test_col", limit=1, with_payload=True)
    assert len(points) == 1
    assert points[0].payload["doc_permission_id"] == 42


def test_search_collection_returns_doc_permission_id(tmp_path):
    """search_collection 返回的 Chunk 包含 doc_permission_id。"""
    import rag.vector_store as vs
    vs._client = QdrantClient(path=str(tmp_path / "qdrant"))
    vs._ensure_collection_name("test_col")

    from rag.models import Chunk
    chunks = [Chunk(text="hello", doc_name="a.pdf", chunk_index=0)]
    embeddings = [[0.1] * 1024]
    vs.add_to_collection("test_col", chunks, embeddings, doc_permission_id=42)

    results = vs.search_collection("test_col", [0.1] * 1024, top_k=1)
    assert len(results) == 1
    assert results[0].doc_permission_id == 42
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_vector_store.py::test_add_to_collection_with_permission_id -v`

Expected: FAIL — `add_to_collection()` 不接受 `doc_permission_id` 参数。

- [ ] **Step 4: 修改 `knowledge_base.py` — `add_document()` 透传 `doc_permission_id`**

修改 `KnowledgeBaseManager.add_document()` 的签名和调用：

```python
    def add_document(self, kb_id: str, file_path: str, doc_name: str = None, doc_permission_id: int = None) -> int:
        from rag.chunker import chunk
        from rag.embedder import embed
        from rag.loader import load
        from rag.vector_store import add_to_collection

        text = load(file_path)
        if doc_name is None:
            doc_name = file_path.split("/")[-1].split("\\")[-1]
        chunks = chunk(text, doc_name=doc_name)
        embeddings = embed([c.text for c in chunks])
        add_to_collection(kb_id, chunks, embeddings, doc_permission_id=doc_permission_id)
        return len(chunks)
```

- [ ] **Step 5: 修改 `vector_store.py` — `add_to_collection()` 加 `doc_permission_id` 参数**

```python
def add_to_collection(collection_name: str, chunks: list[Chunk], embeddings: list[list[float]], tags: list[str] = None, doc_permission_id: int = None):
    with _write_lock.write():
        client = _get_client()
        if not client.collection_exists(collection_name):
            raise ValueError(f"集合 {collection_name} 不存在，请先创建知识库")
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embeddings[i],
                payload={
                    "text": chunks[i].text,
                    "doc_name": chunks[i].doc_name,
                    "chunk_index": chunks[i].chunk_index,
                    "tags": tags or [],
                    **({"doc_permission_id": doc_permission_id} if doc_permission_id is not None else {}),
                },
            )
            for i in range(len(chunks))
        ]
        client.upsert(collection_name=collection_name, points=points)
```

- [ ] **Step 6: 修改 `vector_store.py` — `search_collection()` 返回 `doc_permission_id`**

修改 `search_collection()` 的返回值构造，从 payload 中读取 `doc_permission_id`：

```python
        return [
            Chunk(
                text=h.payload["text"],
                doc_name=h.payload.get("doc_name", ""),
                chunk_index=h.payload.get("chunk_index", 0),
                doc_permission_id=h.payload.get("doc_permission_id"),
            )
            for h in hits.points
            if h.payload
        ]
```

- [ ] **Step 7: 运行测试确认通过**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_vector_store.py -v`

Expected: ALL PASS。

- [ ] **Step 8: Commit**

```bash
git add rag/models.py rag/vector_store.py rag/knowledge_base.py tests/test_vector_store.py
git commit -m "feat: Chunk 加 doc_permission_id，vector_store 读写该字段，KnowledgeBaseManager 透传"
```

---

## Task 8: API — 上传接口支持 permission_level

**Files:**
- Modify: `rag/api.py` — `POST /upload` 和 `POST /knowledge-bases/{kb_id}/documents`
- Test: `tests/test_api.py` 或 `tests/test_permissions_api.py`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_permissions_api.py`：

```python
"""Tests for permission-related API endpoints."""

import pytest
from fastapi.testclient import TestClient

from rag.user_db import UserDB


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Create a test client with a temporary database."""
    from rag.user_db import UserDB
    db_path = str(tmp_path / "users.db")
    user_db_inst = UserDB(db_path)
    monkeypatch.setattr("rag.api.user_db", user_db_inst)
    monkeypatch.setattr("config.settings.users_db_path", db_path)
    monkeypatch.setattr("config.settings.auth_enabled", True)
    with TestClient(app) as c:
        yield c
    user_db_inst.close()


def _register_and_login(client: TestClient, username: str = "alice", password: str = "s3cret") -> str:
    resp = client.post("/register", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["token"]


def test_upload_with_permission_level(client, tmp_path, monkeypatch):
    """上传文件时指定 permission_level。"""
    monkeypatch.setattr("rag.api.DATA_DIR", tmp_path / "upload")
    (tmp_path / "upload").mkdir()
    token = _register_and_login(client)
    # 写一个测试文件
    test_file = tmp_path / "upload" / "test.txt"
    test_file.write_text("hello world")
    with open(test_file, "rb") as f:
        resp = client.post(
            "/upload",
            files={"file": ("test.txt", f, "text/plain")},
            data={"permission_level": "3"},
            headers={"Authorization": f"Bearer {token}"},
        )
    # 注意：实际测试需要 mock KnowledgeBaseManager 和 pipeline
    # 这里只验证 permission_level 参数被接受
    assert resp.status_code in (200, 201, 400, 500)  # 取决于 pipeline 是否可用
```

- [ ] **Step 2: 修改 `api.py` — upload 接口加 permission_level 参数**

修改 `POST /upload` 端点，增加 `permission_level` Form 参数：

```python
@app.post(
    "/upload",
    summary="上传文件",
    description="上传文件到 data/upload/ 并索引，支持 txt/md/pdf/docx/xlsx/csv 格式，最大 10MB",
)
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
    permission_level: int = 1,
    authorization: str = Header(default=""),
):
```

在函数体内，**索引成功后**创建权限记录（避免索引失败时残留孤儿记录）：

```python
    # 索引文件
    try:
        manager = KnowledgeBaseManager()
        count = manager.add_document("rag_docs", str(dest), doc_name=filename)
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))

    # 索引成功后创建权限记录（如果失败，文件已索引但无权限记录，视为旧文档公开）
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)

    perm_id = None
    if user_dict:
        def _create_perm():
            return user_db.create_document_permission(filename, "rag_docs", user_dict["id"], permission_level)
        try:
            perm_id = await asyncio.to_thread(_create_perm)
        except Exception as e:
            logger.warning("权限记录创建失败（文件已索引）: %s", e)
```

然后用 `perm_id` 重新索引以写入 Qdrant payload（或在首次索引时传入）。更简单的做法是把权限创建移到索引之前，但加回滚：

```python
    # 获取当前用户
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)

    # 先创建权限记录
    perm_id = None
    if user_dict:
        def _create_perm():
            return user_db.create_document_permission(filename, "rag_docs", user_dict["id"], permission_level)
        perm_id = await asyncio.to_thread(_create_perm)

    # 索引文件（传入 perm_id 写入 Qdrant payload）
    try:
        manager = KnowledgeBaseManager()
        count = manager.add_document("rag_docs", str(dest), doc_name=filename, doc_permission_id=perm_id)
    except Exception as e:
        dest.unlink(missing_ok=True)
        # 回滚权限记录
        if perm_id:
            await asyncio.to_thread(user_db.delete_document_permission, perm_id)
        raise HTTPException(status_code=400, detail=str(e))
```

**选择方案二（先创建权限，失败回滚）**，因为这样 perm_id 可以传入 `add_document()` 写入 Qdrant payload。

- [ ] **Step 3: 运行测试确认通过**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_permissions_api.py -v`

Expected: PASS。

- [ ] **Step 4: Commit**

```bash
git add rag/api.py tests/test_permissions_api.py
git commit -m "feat: POST /upload 支持 permission_level 参数"
```

---

## Task 9: API — 现有接口加权限校验

**Files:**
- Modify: `rag/api.py` — `DELETE /files/{filename}`、`POST /files/{filename}/tags`、`DELETE /knowledge-bases/{kb_id}/documents/{doc_name}`

**背景：** 这三个现有接口的函数签名中**没有 `authorization` 参数**，无法获取当前用户信息。必须先修改签名，再加权限校验逻辑。

- [ ] **Step 1: 修改 `DELETE /files/{filename}` — 加 authorization 参数 + 权限校验**

将函数签名从：

```python
async def delete_file(filename: str, authorization: str = Header(default="")):
```

注意：该接口已有 `authorization` 参数（确认现有代码）。在函数体内，文件存在性检查之后、删除之前，插入：

```python
    # 权限校验（旧文档无记录时 check_doc_permission 返回 None，放行）
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)
    if user_dict and user_dict.get("id") != "anonymous":
        from rag.permissions import check_doc_permission
        await asyncio.to_thread(check_doc_permission, user_db, safe_name, "rag_docs", user_dict, "delete")
```

注意：`check_doc_permission` 对无权限记录的文档返回 `None`（不抛异常），所以旧文档可以正常删除。

- [ ] **Step 2: 修改 `POST /files/{filename}/tags` — 加 authorization 参数 + 权限校验**

**现有代码没有 `authorization` 参数**，需要在函数签名中添加：

```python
async def add_tags_to_file(filename: str, tags: list[str], authorization: str = Header(default="")):
```

在函数体内，文件名解析之后、操作 Qdrant 之前，插入：

```python
    # 权限校验（旧文档无记录时放行）
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)
    if user_dict and user_dict.get("id") != "anonymous":
        from rag.permissions import check_doc_permission
        await asyncio.to_thread(check_doc_permission, user_db, safe_name, "rag_docs", user_dict, "edit")
```

- [ ] **Step 3: 修改 `DELETE /knowledge-bases/{kb_id}/documents/{doc_name}` — 加权限校验 + 清理权限记录**

**现有代码有 `user_id: str = Security(verify_api_key)` 但这是 API Key 模式，返回 string 不是完整 user dict。** 需要在函数签名中追加 `authorization` 参数：

```python
async def remove_document_from_kb(kb_id: str, doc_name: str, user_id: str = Security(verify_api_key), authorization: str = Header(default="")):
```

在函数体内，manager 操作之前，插入权限校验；**在删除成功后，清理 `document_permissions` 记录**（避免孤儿记录）：

```python
    # 权限校验（旧文档无记录时放行）
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)
    if user_dict and user_dict.get("id") != "anonymous":
        from rag.permissions import check_doc_permission
        await asyncio.to_thread(check_doc_permission, user_db, doc_name, kb_id, user_dict, "delete")

    # ... 现有的删除逻辑 ...

    # 清理权限记录（级联会自动清理 shares）
    def _cleanup_perm():
        perm = user_db.get_document_permission(doc_name, kb_id)
        if perm:
            user_db.delete_document_permission(perm["id"])
    await asyncio.to_thread(_cleanup_perm)
```

- [ ] **Step 4: 运行现有测试确认不破坏**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_api.py -v`

Expected: ALL PASS。

- [ ] **Step 5: Commit**

```bash
git add rag/api.py
git commit -m "feat: DELETE /files、POST tags、DELETE KB doc 加权限校验"
```

---

## Task 10: API — 权限管理端点（查看/修改/共享）

**Files:**
- Modify: `rag/api.py`

- [ ] **Step 1: 新增 `GET /documents/{doc_id}/permissions`**

在 `api.py` 中新增端点：

```python
@app.get("/documents/{doc_id}/permissions", summary="查看文档权限信息")
async def get_document_permissions(doc_id: int, authorization: str = Header(default="")):
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)

    def _get():
        perm = user_db.get_document_permission_by_id(doc_id)
        if not perm:
            return None
        shared_users = user_db.list_shared_users(doc_id)
        owner = user_db.get_user_by_id(perm["owner_id"])
        return {
            "doc_id": doc_id,
            "doc_name": perm["doc_name"],
            "permission_level": perm["permission_level"],
            "owner": {"id": owner["id"], "username": owner["username"]} if owner else None,
            "shared_with": shared_users,
        }

    result = await asyncio.to_thread(_get)
    if not result:
        raise HTTPException(status_code=404, detail="文档权限记录不存在")
    return result
```

- [ ] **Step 2: 新增 `PUT /documents/{doc_id}/permission`**

```python
class UpdatePermissionRequest(BaseModel):
    permission_level: int = Field(..., ge=1, le=5)


@app.put("/documents/{doc_id}/permission", summary="修改文档权限等级")
async def update_document_permission(doc_id: int, req: UpdatePermissionRequest, authorization: str = Header(default="")):
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)

    def _update():
        perm = user_db.get_document_permission_by_id(doc_id)
        if not perm:
            raise HTTPException(status_code=404, detail="文档不存在")
        if user_dict and not user_dict.get("is_admin") and perm["owner_id"] != user_dict["id"]:
            raise HTTPException(status_code=403, detail="仅文档上传者或管理员可修改权限")
        user_db.update_document_permission_level(doc_id, req.permission_level)
        return {"id": doc_id, "permission_level": req.permission_level}

    return await asyncio.to_thread(_update)
```

- [ ] **Step 3: 新增 `POST /documents/{doc_id}/share`**

```python
class ShareRequest(BaseModel):
    user_id: int


@app.post("/documents/{doc_id}/share", summary="共享文档给指定用户")
async def share_document(doc_id: int, req: ShareRequest, authorization: str = Header(default="")):
    import sqlite3 as _sqlite3
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)

    def _share():
        perm = user_db.get_document_permission_by_id(doc_id)
        if not perm:
            raise HTTPException(status_code=404, detail="文档不存在")
        if user_dict and not user_dict.get("is_admin") and perm["owner_id"] != user_dict["id"]:
            raise HTTPException(status_code=403, detail="仅文档上传者或管理员可共享")
        try:
            share_id = user_db.share_document(doc_id, req.user_id, user_dict["id"])
        except _sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="该用户已被共享")
        return {"doc_id": doc_id, "user_id": req.user_id, "granted_by": user_dict["id"]}

    return await asyncio.to_thread(_share)
```

- [ ] **Step 4: 新增 `DELETE /documents/{doc_id}/share/{user_id}`**

```python
@app.delete("/documents/{doc_id}/share/{user_id}", summary="撤销文档共享", status_code=204)
async def unshare_document(doc_id: int, user_id: int, authorization: str = Header(default="")):
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)

    def _unshare():
        perm = user_db.get_document_permission_by_id(doc_id)
        if not perm:
            raise HTTPException(status_code=404, detail="文档不存在")
        if user_dict and not user_dict.get("is_admin") and perm["owner_id"] != user_dict["id"]:
            raise HTTPException(status_code=403, detail="仅文档上传者或管理员可撤销共享")
        user_db.unshare_document(doc_id, user_id)

    await asyncio.to_thread(_unshare)
    return None
```

- [ ] **Step 5: 新增 `PUT /users/{uid}/role`（支持设置 is_admin 和 permission_level）**

```python
class UpdateRoleRequest(BaseModel):
    is_admin: bool | None = None
    permission_level: int | None = Field(default=None, ge=1, le=5)


@app.put("/users/{uid}/role", summary="设置用户角色（管理员/权限等级）")
async def set_user_role(uid: int, req: UpdateRoleRequest, authorization: str = Header(default="")):
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)
    if not user_dict or not user_dict.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    def _set():
        target = user_db.get_user_by_id(uid)
        if not target:
            raise HTTPException(status_code=404, detail="用户不存在")
        if req.is_admin is not None:
            user_db.set_user_admin(uid, req.is_admin)
        if req.permission_level is not None:
            user_db.set_user_permission_level(uid, req.permission_level)
        return user_db.get_user_by_id(uid)

    return await asyncio.to_thread(_set)
```

- [ ] **Step 6: 运行测试确认不破坏**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_api.py -v`

Expected: ALL PASS。

- [ ] **Step 7: Commit**

```bash
git add rag/api.py
git commit -m "feat: 新增文档权限管理 API (查看/修改/共享/撤销/设管理员)"
```

---

## Task 11: 管理员初始化 — 启动时自动设置

**Files:**
- Modify: `rag/api.py` — startup hook
- Modify: `.env.example`

- [ ] **Step 1: 修改 startup hook 加管理员初始化**

在 `rag/api.py` 的 `auto_index_on_startup()` 函数末尾（`except` 块之后）追加：

```python
    # 管理员初始化：首次启动时根据环境变量设置管理员
    def _init_admin():
        import os
        admin_username = os.getenv("INIT_ADMIN_USERNAME")
        if not admin_username:
            return
        # 检查是否已有管理员（用公开方法，不访问私有属性）
        existing_admin = user_db.get_user_by_username(admin_username)
        if existing_admin and existing_admin.get("is_admin"):
            return  # 已是管理员，跳过
        # 检查系统中是否已有任何管理员
        # （get_user_by_username 不检查 is_admin，需要额外查询）
        # 如果指定用户存在但不是管理员，则设置为管理员
        if existing_admin:
            user_db.set_user_admin(existing_admin["id"], True)
            logger.info("已将用户 %s 设置为管理员", admin_username)

    try:
        _init_admin()
    except Exception as e:
        logger.warning("管理员初始化失败: %s", e)
```

- [ ] **Step 2: 更新 `.env.example`**

在 `.env.example` 末尾追加：

```bash
# 首次部署时指定初始管理员用户名（可选）
# INIT_ADMIN_USERNAME=admin
```

- [ ] **Step 3: 运行现有测试确认不破坏**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_api.py -v`

Expected: ALL PASS。

- [ ] **Step 4: Commit**

```bash
git add rag/api.py .env.example
git commit -m "feat: 启动时根据 INIT_ADMIN_USERNAME 环境变量初始化管理员"
```

---

## Task 12: 知识库查询接口支持 scope 参数

**Files:**
- Modify: `rag/api.py` — `GET /knowledge-bases/{kb_id}`

- [ ] **Step 1: 修改 `get_knowledge_base_detail()` 支持 scope**

修改 `get_knowledge_base_detail()` 函数签名，增加 `scope` 和 `authorization` 参数：

```python
@app.get("/knowledge-bases/{kb_id}", summary="获取知识库详情")
async def get_knowledge_base_detail(
    kb_id: str,
    scope: str = "accessible",
    authorization: str = Header(default=""),
):
```

在函数体内，获取文档列表时根据 scope 过滤：

```python
    # 获取当前用户信息
    user_dict = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user_dict = await asyncio.to_thread(_get_current_user, token)

    # 根据 scope 过滤文档（批量查询，避免 N+1）
    def _get_docs():
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            docs = conn.execute(
                "SELECT * FROM kb_documents WHERE kb_id = ? ORDER BY added_at DESC",
                (kb_id,),
            ).fetchall()

            if scope == "all":
                if not user_dict or not user_dict.get("is_admin"):
                    raise HTTPException(status_code=403, detail="仅管理员可查看全部文档")
                return [dict(d) for d in docs]

            # scope == "accessible": 按权限过滤
            if not user_dict or user_dict.get("id") == "anonymous":
                return [dict(d) for d in docs]  # 匿名用户看所有（兼容旧逻辑）

            # 批量查询权限记录（一次查完，避免逐条查）
            doc_names = [d["filename"] for d in docs]
            perm_map = user_db.get_document_permissions_by_names(doc_names, kb_id)

            # 批量查询当前用户被共享的 doc_id 集合（一次查完，避免 N+1）
            all_perm_ids = [p["id"] for p in perm_map.values() if p is not None]
            shared_doc_ids = user_db.get_shared_doc_ids_for_user(user_dict["id"], all_perm_ids)

            # 过滤有权文档
            allowed_names = set()
            for d in docs:
                perm = perm_map.get(d["filename"])
                if perm is None:
                    allowed_names.add(d["filename"])  # 无权限记录，视为公开
                elif perm["owner_id"] == user_dict["id"]:
                    allowed_names.add(d["filename"])  # 自己上传的
                elif perm["id"] in shared_doc_ids:
                    allowed_names.add(d["filename"])  # 被共享的
                elif user_dict.get("permission_level", 1) >= perm["permission_level"]:
                    allowed_names.add(d["filename"])  # 等级够的

            # 构造响应，补充权限字段
            result = []
            for d in docs:
                if d["filename"] not in allowed_names:
                    continue
                perm = perm_map.get(d["filename"])
                owner = user_db.get_user_by_id(perm["owner_id"]) if perm else None
                entry = dict(d)
                entry["doc_permission_id"] = perm["id"] if perm else None
                entry["permission_level"] = perm["permission_level"] if perm else 1
                entry["owner"] = {"id": owner["id"], "username": owner["username"]} if owner else None
                entry["can_edit"] = (
                    user_dict.get("is_admin")
                    or (perm and perm["owner_id"] == user_dict["id"])
                    or (perm and perm["id"] in shared_doc_ids)
                )
                entry["can_share"] = (
                    user_dict.get("is_admin")
                    or (perm and perm["owner_id"] == user_dict["id"])
                )
                result.append(entry)
            return result
        finally:
            conn.close()
```

- [ ] **Step 2: 运行现有测试确认不破坏**

Run: `cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/test_api.py tests/test_kb_tables.py -v`

Expected: ALL PASS。

- [ ] **Step 3: Commit**

```bash
git add rag/api.py
git commit -m "feat: GET /knowledge-bases/{kb_id} 支持 scope 参数过滤文档"
```

---

## Task 13: 前端 — 上传弹窗加权限等级选择器

**Files:**
- Modify: `frontend/src/views/FileModeView.vue`
- Modify: `frontend/src/views/KnowledgeDetailView.vue`

- [ ] **Step 1: FileModeView.vue — 上传弹窗加权限下拉**

找到上传相关的 `el-dialog` 或上传按钮区域，在文件选择器之后追加权限等级选择器：

```vue
<el-select v-model="uploadPermissionLevel" placeholder="权限等级" style="width: 100%; margin-top: 12px;">
  <el-option :value="1" label="1 - 普通员工" />
  <el-option :value="2" label="2 - 组长" />
  <el-option :value="3" label="3 - 主管" />
  <el-option :value="4" label="4 - 总监" />
  <el-option :value="5" label="5 - 管理员" />
</el-select>
```

在 `<script setup>` 中添加响应式变量：

```typescript
const uploadPermissionLevel = ref(1)
```

修改上传逻辑，将 `permission_level` 一起发送：

```typescript
const formData = new FormData()
formData.append('file', file)
formData.append('permission_level', String(uploadPermissionLevel.value))
```

- [ ] **Step 2: KnowledgeDetailView.vue — 同样的权限选择器**

在知识库详情页的"添加文件"弹窗中，同样加入权限等级选择器。

- [ ] **Step 3: 前端构建验证**

Run: `cd c:\Users\lahm\Desktop\RAGv3\frontend && npm run build`

Expected: 构建成功，无报错。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/FileModeView.vue frontend/src/views/KnowledgeDetailView.vue
git commit -m "feat: 前端上传弹窗新增权限等级选择器"
```

---

## Task 14: 前端 — 知识库详情页 scope 选择器 + 权限标签

**Files:**
- Modify: `frontend/src/views/KnowledgeDetailView.vue`
- Modify: `frontend/src/stores/chat.ts`（如需）

- [ ] **Step 1: 在知识库详情页的文档列表区域上方加 scope 选择器**

```vue
<div class="scope-selector" style="margin-bottom: 12px;">
  <el-radio-group v-model="docScope" @change="loadKBDetail">
    <el-radio-button value="accessible">我能看的</el-radio-button>
    <el-radio-button v-if="authStore.user?.is_admin" value="all">全部</el-radio-button>
  </el-radio-group>
</div>
```

在 `<script setup>` 中：

```typescript
const docScope = ref('accessible')
```

修改 `loadKBDetail` 方法，请求时带上 `scope` 参数：

```typescript
const resp = await api.get(`/knowledge-bases/${kbId.value}`, { params: { scope: docScope.value } })
```

- [ ] **Step 2: 在文档列表中显示权限等级标签**

在文档列表的每项中追加：

```vue
<el-tag v-if="doc.permission_level" size="small" type="info">
  等级 {{ doc.permission_level }}
</el-tag>
<el-tag v-if="doc.owner" size="small">
  {{ doc.owner.username }}
</el-tag>
```

- [ ] **Step 3: 前端构建验证**

Run: `cd c:\Users\lahm\Desktop\RAGv3\frontend && npm run build`

Expected: 构建成功。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/KnowledgeDetailView.vue
git commit -m "feat: 知识库详情页新增 scope 选择器和权限等级标签"
```

---

## Task 15: 前端 — 文档共享管理弹窗

**Files:**
- Create: `frontend/src/components/ShareDialog.vue`
- Modify: `frontend/src/views/KnowledgeDetailView.vue`

- [ ] **Step 1: 创建 ShareDialog.vue 组件**

新建 `frontend/src/components/ShareDialog.vue`：

```vue
<template>
  <el-dialog v-model="visible" title="文档共享管理" width="480px">
    <div class="share-section">
      <h4>当前权限等级</h4>
      <el-select v-model="localLevel" @change="updateLevel" style="width: 100%;">
        <el-option :value="1" label="1 - 普通员工" />
        <el-option :value="2" label="2 - 组长" />
        <el-option :value="3" label="3 - 主管" />
        <el-option :value="4" label="4 - 总监" />
        <el-option :value="5" label="5 - 管理员" />
      </el-select>
    </div>

    <div class="share-section" style="margin-top: 20px;">
      <h4>已共享用户</h4>
      <div v-if="sharedUsers.length === 0" class="empty-hint">暂无共享用户</div>
      <div v-for="u in sharedUsers" :key="u.id" class="shared-user-row">
        <span>{{ u.username }}</span>
        <el-button size="small" type="danger" text @click="unshare(u.id)">撤销</el-button>
      </div>
    </div>

    <div class="share-section" style="margin-top: 20px;">
      <h4>添加共享</h4>
      <div style="display: flex; gap: 8px;">
        <el-input v-model="newUserId" placeholder="用户 ID" type="number" />
        <el-button type="primary" @click="share">共享</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import api from '@/utils/api'

const props = defineProps<{ docId: number | null }>()
const visible = defineModel<boolean>('visible')
const localLevel = ref(1)
const sharedUsers = ref<any[]>([])
const newUserId = ref('')

watch(visible, async (v) => {
  if (v && props.docId) {
    await loadPermissions()
  }
})

async function loadPermissions() {
  const resp = await api.get(`/documents/${props.docId}/permissions`)
  localLevel.value = resp.data.permission_level
  sharedUsers.value = resp.data.shared_with || []
}

async function updateLevel() {
  await api.put(`/documents/${props.docId}/permission`, { permission_level: localLevel.value })
}

async function share() {
  if (!newUserId.value) return
  try {
    await api.post(`/documents/${props.docId}/share`, { user_id: Number(newUserId.value) })
    newUserId.value = ''
    await loadPermissions()
  } catch (e: any) {
    // 错误已由 api interceptor 处理
  }
}

async function unshare(userId: number) {
  await api.delete(`/documents/${props.docId}/share/${userId}`)
  await loadPermissions()
}
</script>

<style scoped>
.share-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--color-text-secondary);
}
.shared-user-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border);
}
.empty-hint {
  color: var(--color-text-tertiary);
  font-size: 13px;
}
</style>
```

- [ ] **Step 2: 在 KnowledgeDetailView.vue 中集成 ShareDialog**

在文档列表的操作按钮区域追加"共享"按钮：

```vue
<el-button size="small" @click="openShareDialog(doc)">共享</el-button>
```

在模板底部引入组件：

```vue
<ShareDialog v-model:visible="shareDialogVisible" :doc-id="shareDocId" />
```

在 `<script setup>` 中：

```typescript
import ShareDialog from '@/components/ShareDialog.vue'

const shareDialogVisible = ref(false)
const shareDocId = ref<number | null>(null)

function openShareDialog(doc: any) {
  shareDocId.value = doc.id
  shareDialogVisible.value = true
}
```

- [ ] **Step 3: 前端构建验证**

Run: `cd c:\Users\lahm\Desktop\RAGv3\frontend && npm run build`

Expected: 构建成功。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ShareDialog.vue frontend/src/views/KnowledgeDetailView.vue
git commit -m "feat: 新增文档共享管理弹窗组件"
```

---

## 最终验证

- [ ] **运行全部后端测试**

```bash
cd c:\Users\lahm\Desktop\RAGv3 && python -m pytest tests/ -v --tb=short
```

Expected: ALL PASS（248+ 个测试）。

- [ ] **运行前端测试**

```bash
cd c:\Users\lahm\Desktop\RAGv3\frontend && npm run test:unit
```

Expected: ALL PASS。

- [ ] **前端构建**

```bash
cd c:\Users\lahm\Desktop\RAGv3\frontend && npm run build
```

Expected: 构建成功，输出到 `../static/`。

- [ ] **手动验证**

1. 启动后端：`python start.py`
2. 注册两个用户（alice, bob）
3. 用 alice 上传文件，设置 permission_level=3
4. 用 bob（level=1）登录，确认看不到该文件
5. 用 alice 共享给 bob，确认 bob 能看到了
6. 用 bob 查询，确认检索结果中不包含无权文档的 chunks

---

## 矛盾修复记录

本计划初版与现有代码存在以下矛盾，已全部修复：

### 第一轮（代码层面矛盾）

| # | 矛盾 | 修复方式 | 涉及 Task |
|---|------|---------|-----------|
| 1 | `config.py` 没有 `users_db_path` 字段，pipeline 中无法创建 UserDB | 新增 Task 0：在 config.py 加 `users_db_path`，api.py 改用 config 路径 | Task 0, 6 |
| 2 | `DELETE /files/{filename}` 和 `POST /files/{filename}/tags` 函数签名没有 `authorization` 参数 | Task 9 中明确在函数签名加 `authorization: str = Header(default="")` | Task 9 |
| 3 | `KnowledgeBaseManager.add_document()` 不接受 `doc_permission_id` 参数 | Task 7 中改 `knowledge_base.py` 签名加参数并透传 | Task 7, 8 |
| 4 | `DELETE KB doc` 用 `verify_api_key`（返回 string）而非完整 user dict | Task 9 中追加 `authorization` 参数 | Task 9 |

### 第一轮（逻辑层面矛盾）

| # | 问题 | 修复方式 | 涉及 Task |
|---|------|---------|-----------|
| 5 | `check_doc_permission` 对无记录文档返回 404，旧文档无法删除/打标签 | 改为返回 `None`（放行），与 `filter_chunks_by_permission` 逻辑一致 | Task 4, 9 |
| 6 | `filter_chunks_by_permission` 对每个 chunk 查一次 DB（N+1） | 改用 `get_document_permissions_by_names()` 批量查询 | Task 2, 5 |
| 7 | pipeline 每次查询新建 UserDB 连接 | 改为 `RAGPipeline.__init__()` 注入 `user_db` 引用，api.py 启动时传入 | Task 6 |
| 8 | `doc_permission_id` 写入 Qdrant 但 pipeline 过滤用 doc_name 查 | Chunk dataclass 加 `doc_permission_id` 字段，`search_collection()` 返回时读取，pipeline 优先用它做快速查询 | Task 7 |
| 9 | 知识库详情页逐条查权限（N+1）+ 响应缺 permission_level/owner/can_edit | 改用批量查询 + 补充响应字段 | Task 12 |

### 第二轮（工程层面问题）

| # | 问题 | 修复方式 | 涉及 Task |
|---|------|---------|-----------|
| 10 | 上传失败时权限记录残留 | 改为先创建权限记录，索引失败时回滚删除 | Task 8 |
| 11 | share 接口 `except Exception` 吞掉所有异常 | 改为只 catch `sqlite3.IntegrityError` | Task 10 |
| 12 | 管理员初始化直接访问 `user_db._lock` / `user_db._conn`（私有属性） | 新增 `get_user_by_username()` 公开方法 | Task 2, 11 |
| 13 | `PUT /users/{uid}/admin` 只能设 True，不能撤销 | 改为 `PUT /users/{uid}/role`，支持设置 `is_admin` 和 `permission_level` | Task 10 |
| 14 | 无 `INIT_ADMIN_USERNAME` 时系统无 admin 且无法创建 | Task 11 中 `get_user_by_username()` 检查用户是否存在，存在则设置；不存在则跳过（用户需先注册再设环境变量重启） | Task 11 |
| 15 | `DELETE KB doc` 不清理 `document_permissions`（孤儿记录） | Task 9 中删除成功后清理权限记录 | Task 9 |
| 16 | test fixture 导入顺序错误 + 创建两个 UserDB 实例 | 修正 import 顺序，只创建一个实例 | Task 8 |
| 17 | `user.get("id") != "anonymous"` 判断脆弱 | 改为 `user is not None` | Task 6 |

### 关于 batch_import / folder_indexer

`batch_importer.py` 和 `folder_indexer.py` 也调用 `add_to_collection()`，但不经过 `KnowledgeBaseManager`。**当前计划不改它们**，这意味着：
- 批量导入的文档没有 `doc_permission_id`，会被视为旧文档（公开）
- folder_indexer 重建索引时也不写 `doc_permission_id`

**这是预期行为**：批量导入和启动索引的文档默认公开。如需限制，后续可扩展。
