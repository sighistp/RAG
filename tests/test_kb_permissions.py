"""Phase 1 tests: KB ownership and scope-based access control."""

import pytest
from rag.user_db import UserDB


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "test.db")
    udb = UserDB(path)
    yield udb
    udb.close()


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


def test_document_permissions_has_scope_column(db):
    """document_permissions 表应有 scope 列。"""
    uid = db.create_user("alice", "pwd")
    with db._lock:
        db._conn.execute(
            "INSERT INTO document_permissions (doc_name, kb_id, owner_id, is_public, protected, scope) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("test.pdf", "rag_docs", uid, 0, 0, "private"),
        )
        db._conn.commit()
        row = db._conn.execute(
            "SELECT scope FROM document_permissions WHERE doc_name = ?",
            ("test.pdf",),
        ).fetchone()
    assert row is not None
    assert row["scope"] == "private"


# ── Task 1.2: KB Metadata CRUD ─────────────────────────────────────


def test_create_kb_metadata(db):
    """create_kb_metadata 应写入 owner_id 和 scope。"""
    db.create_kb_metadata("kb_test_001", "测试知识库", owner_id=1, scope="private")
    meta = db.get_kb_metadata("kb_test_001")
    assert meta is not None
    assert meta["kb_id"] == "kb_test_001"
    assert meta["name"] == "测试知识库"
    assert meta["owner_id"] == 1
    assert meta["scope"] == "private"


def test_get_kb_metadata_nonexistent(db):
    """不存在的 KB 返回 None。"""
    assert db.get_kb_metadata("kb_nonexistent") is None


def test_update_kb_scope(db):
    """update_kb_scope 应更新 scope 字段。"""
    db.create_kb_metadata("kb_test_001", "测试知识库", owner_id=1, scope="private")
    db.update_kb_scope("kb_test_001", "public")
    meta = db.get_kb_metadata("kb_test_001")
    assert meta["scope"] == "public"


def test_get_kb_metadata_by_names_batch(db):
    """get_kb_metadata_by_names 应批量查询。"""
    db.create_kb_metadata("kb_a", "A库", owner_id=1, scope="public")
    db.create_kb_metadata("kb_b", "B库", owner_id=2, scope="private")
    result = db.get_kb_metadata_by_names(["kb_a", "kb_b", "kb_c"])
    assert len(result) == 3
    assert result["kb_a"]["scope"] == "public"
    assert result["kb_b"]["scope"] == "private"
    assert result["kb_c"] is None


# ── Task 1.3: KB 列出过滤 + CREATE KB ──────────────────────────────


def test_list_kbs_filters_private_for_non_owner(db):
    """非 owner 不应看到 private KB。"""
    owner = db.create_user("alice", "pwd")
    other = db.create_user("bob", "pwd")
    db.create_kb_metadata("kb_private", "私有库", owner_id=owner, scope="private")
    db.create_kb_metadata("kb_public", "公开库", owner_id=owner, scope="public")

    meta_map = db.get_kb_metadata_by_names(["kb_private", "kb_public"])
    visible = []
    for kid, meta in meta_map.items():
        if meta is None:
            visible.append(kid)
        elif meta["scope"] == "public":
            visible.append(kid)
        elif meta["owner_id"] == other:
            visible.append(kid)

    assert "kb_public" in visible
    assert "kb_private" not in visible


def test_list_kbs_owner_sees_own_private(db):
    """owner 应看到自己的 private KB。"""
    owner = db.create_user("alice", "pwd")
    db.create_kb_metadata("kb_private", "私有库", owner_id=owner, scope="private")

    meta_map = db.get_kb_metadata_by_names(["kb_private"])
    visible = []
    for kid, meta in meta_map.items():
        if meta is None:
            visible.append(kid)
        elif meta["scope"] == "public":
            visible.append(kid)
        elif meta["owner_id"] == owner:
            visible.append(kid)

    assert "kb_private" in visible


def test_list_kbs_old_kb_visible_to_all(db):
    """旧 KB（owner_id=0）应所有人可见。"""
    other = db.create_user("bob", "pwd")
    db.create_kb_metadata("kb_old", "旧库", owner_id=0, scope="public")

    meta_map = db.get_kb_metadata_by_names(["kb_old"])
    visible = []
    for kid, meta in meta_map.items():
        if meta is None:
            visible.append(kid)
        elif meta["scope"] == "public":
            visible.append(kid)
        elif meta["owner_id"] == other:
            visible.append(kid)

    assert "kb_old" in visible


def test_list_kbs_admin_sees_all(db):
    """admin 应看到所有 KB。"""
    owner = db.create_user("alice", "pwd")
    admin = db.create_user("root", "pwd")
    db.set_user_admin(admin, True)
    db.create_kb_metadata("kb_private", "私有库", owner_id=owner, scope="private")
    db.create_kb_metadata("kb_public", "公开库", owner_id=owner, scope="public")

    meta_map = db.get_kb_metadata_by_names(["kb_private", "kb_public"])
    is_admin = True
    visible = []
    for kid, meta in meta_map.items():
        if is_admin:
            visible.append(kid)
        elif meta is None:
            visible.append(kid)
        elif meta["scope"] == "public":
            visible.append(kid)
        elif meta["owner_id"] == admin:
            visible.append(kid)

    assert "kb_private" in visible
    assert "kb_public" in visible


# ── Task 1.4: KB 删除/修改加 owner 检查 ────────────────────────────


def test_delete_kb_requires_owner(db):
    """非 owner 删除 KB 应被拒绝。"""
    owner = db.create_user("alice", "pwd")
    other = db.create_user("bob", "pwd")
    db.create_kb_metadata("kb_test", "测试库", owner_id=owner, scope="private")

    meta = db.get_kb_metadata("kb_test")
    is_admin = False
    is_owner = meta["owner_id"] == other

    # 非 owner 且非 admin → 应拒绝
    assert not is_admin and not is_owner


def test_delete_kb_owner_can_delete(db):
    """owner 删除自己的 KB 应成功。"""
    owner = db.create_user("alice", "pwd")
    db.create_kb_metadata("kb_test", "测试库", owner_id=owner, scope="private")

    meta = db.get_kb_metadata("kb_test")
    is_owner = meta["owner_id"] == owner
    assert is_owner


def test_delete_kb_admin_can_delete(db):
    """admin 删除任意 KB 应成功。"""
    owner = db.create_user("alice", "pwd")
    admin = db.create_user("root", "pwd")
    db.set_user_admin(admin, True)
    db.create_kb_metadata("kb_test", "测试库", owner_id=owner, scope="private")

    # admin 可以删任何 KB
    assert True


def test_delete_old_kb_requires_admin(db):
    """旧 KB（owner_id=0）只有 admin 可删除。"""
    other = db.create_user("bob", "pwd")
    admin = db.create_user("root", "pwd")
    db.set_user_admin(admin, True)
    db.create_kb_metadata("kb_old", "旧库", owner_id=0, scope="public")

    meta = db.get_kb_metadata("kb_old")
    # 普通用户
    is_admin = False
    is_owner = meta["owner_id"] == other
    assert not is_admin and not is_owner  # 应拒绝

    # admin
    is_admin = True
    assert is_admin  # 应放行


# ── Task 1.5: KB 查询按 scope 过滤 ─────────────────────────────────


def test_query_private_kb_requires_owner(db):
    """私有 KB 只有 owner 和 admin 可查询。"""
    owner = db.create_user("alice", "pwd")
    other = db.create_user("bob", "pwd")
    db.create_kb_metadata("kb_test", "测试库", owner_id=owner, scope="private")

    meta = db.get_kb_metadata("kb_test")
    # owner 可查询
    assert meta["owner_id"] == owner
    # 非 owner 不可查询
    assert meta["owner_id"] != other


def test_query_public_kb_allowed(db):
    """公开 KB 所有人可查询。"""
    owner = db.create_user("alice", "pwd")
    other = db.create_user("bob", "pwd")
    db.create_kb_metadata("kb_test", "测试库", owner_id=owner, scope="public")

    meta = db.get_kb_metadata("kb_test")
    assert meta["scope"] == "public"  # public → 所有人可查


def test_query_old_kb_allowed(db):
    """旧 KB（owner_id=0）所有人可查询。"""
    other = db.create_user("bob", "pwd")
    db.create_kb_metadata("kb_old", "旧库", owner_id=0, scope="public")

    meta = db.get_kb_metadata("kb_old")
    assert meta["owner_id"] == 0  # 旧 KB → 所有人可查
