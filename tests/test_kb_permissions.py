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
