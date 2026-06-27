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
