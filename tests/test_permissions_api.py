"""Tests for permission-related API endpoints."""

import pytest
from rag.user_db import UserDB


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "test.db")
    udb = UserDB(path)
    yield udb
    udb.close()


def test_create_user_with_permission_fields(db):
    """Verify users have permission_level and is_admin after creation."""
    uid = db.create_user("alice", "s3cret")
    user = db.get_user_by_id(uid)
    assert "permission_level" in user
    assert "is_admin" in user


def test_document_permission_crud(db):
    """Full CRUD for document_permissions."""
    uid = db.create_user("alice", "s3cret")
    doc_id = db.create_document_permission("test.pdf", "kb1", uid, 3)
    assert doc_id > 0

    perm = db.get_document_permission("test.pdf", "kb1")
    assert perm["permission_level"] == 3
    assert perm["owner_id"] == uid

    db.update_document_permission_level(doc_id, 5)
    perm = db.get_document_permission_by_id(doc_id)
    assert perm["permission_level"] == 5

    db.delete_document_permission(doc_id)
    assert db.get_document_permission_by_id(doc_id) is None
