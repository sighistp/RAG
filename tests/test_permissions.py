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
