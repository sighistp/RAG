"""Tests for rag.user_db.UserDB."""

import pytest

from rag.user_db import UserDB


@pytest.fixture()
def db(tmp_path):
    """Yield a fresh UserDB backed by a temporary SQLite file."""
    path = str(tmp_path / "test.db")
    udb = UserDB(path)
    yield udb
    udb.close()


# -- Users -----------------------------------------------------------------


def test_create_user(db):
    uid = db.create_user("alice", "s3cret")
    assert isinstance(uid, int) and uid > 0


def test_create_user_duplicate(db):
    db.create_user("alice", "s3cret")
    with pytest.raises(ValueError, match="already exists"):
        db.create_user("alice", "other")


def test_authenticate_user(db):
    db.create_user("alice", "s3cret")
    result = db.authenticate("alice", "s3cret")
    assert result is not None
    assert result["username"] == "alice"


def test_authenticate_wrong_password(db):
    db.create_user("alice", "s3cret")
    assert db.authenticate("alice", "wrong") is None


def test_authenticate_nonexistent(db):
    assert db.authenticate("nobody", "pwd") is None


def test_get_user_by_id(db):
    uid = db.create_user("alice", "s3cret")
    result = db.get_user_by_id(uid)
    assert result is not None
    assert result["id"] == uid
    assert result["username"] == "alice"


# -- Conversations ---------------------------------------------------------


def test_create_conversation(db):
    uid = db.create_user("alice", "s3cret")
    cid = db.create_conversation(uid, "Hello")
    assert isinstance(cid, int) and cid > 0


def test_list_conversations(db):
    uid = db.create_user("alice", "s3cret")
    db.create_conversation(uid, "First")
    db.create_conversation(uid, "Second")
    convos = db.list_conversations(uid)
    assert len(convos) == 2
    titles = {c["title"] for c in convos}
    assert titles == {"First", "Second"}


def test_delete_conversation(db):
    uid = db.create_user("alice", "s3cret")
    cid = db.create_conversation(uid, "Temp")
    db.add_message(cid, "user", "hi")
    assert db.delete_conversation(cid, uid) is True
    assert db.list_conversations(uid) == []
    assert db.get_messages(cid, uid) == []


# -- Messages --------------------------------------------------------------


def test_add_message(db):
    uid = db.create_user("alice", "s3cret")
    cid = db.create_conversation(uid, "Chat")
    mid = db.add_message(cid, "user", "hello")
    assert isinstance(mid, int) and mid > 0
    msgs = db.get_messages(cid, uid)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "hello"


# -- Feedback --------------------------------------------------------------


def test_add_feedback(db):
    uid = db.create_user("alice", "s3cret")
    cid = db.create_conversation(uid, "Chat")
    mid = db.add_message(cid, "assistant", "answer")
    fid = db.add_feedback(mid, uid, 1, "helpful")
    assert isinstance(fid, int) and fid > 0


# -- Permission fields on users table ----------------------------------------


def test_user_default_is_not_admin(db):
    """新建用户默认 is_admin=False，不返回 permission_level。"""
    uid = db.create_user("alice", "s3cret")
    user = db.get_user_by_id(uid)
    assert user["is_admin"] is False
    assert "permission_level" not in user


def test_set_user_admin(db):
    uid = db.create_user("alice", "s3cret")
    db.set_user_admin(uid, True)
    user = db.get_user_by_id(uid)
    assert user["is_admin"] is True


# -- Document Permissions ----------------------------------------------------


def test_create_document_permission(db):
    """上传文档时创建权限记录（默认私有）。"""
    uid = db.create_user("alice", "s3cret")
    doc_id = db.create_document_permission("report.pdf", "rag_docs", uid)
    assert isinstance(doc_id, int) and doc_id > 0


def test_get_document_permission_by_name(db):
    uid = db.create_user("alice", "s3cret")
    db.create_document_permission("report.pdf", "rag_docs", uid, is_public=False)
    perm = db.get_document_permission("report.pdf", "rag_docs")
    assert perm is not None
    assert perm["doc_name"] == "report.pdf"
    assert perm["owner_id"] == uid
    assert perm["is_public"] is False
    assert perm["protected"] is False


def test_get_document_permission_nonexistent(db):
    """不存在的文档返回 None。"""
    assert db.get_document_permission("nope.pdf", "rag_docs") is None


def test_toggle_document_visibility(db):
    """切换文档公开/私有状态。"""
    uid = db.create_user("alice", "s3cret")
    doc_id = db.create_document_permission("report.pdf", "rag_docs", uid, is_public=False)
    new_val = db.toggle_document_visibility(doc_id)
    assert new_val is True
    perm = db.get_document_permission_by_id(doc_id)
    assert perm["is_public"] is True


def test_delete_document_permission(db):
    uid = db.create_user("alice", "s3cret")
    doc_id = db.create_document_permission("report.pdf", "rag_docs", uid)
    db.delete_document_permission(doc_id)
    assert db.get_document_permission_by_id(doc_id) is None


def test_document_permission_unique_per_kb(db):
    """同一知识库内同名文档只能有一条权限记录。"""
    uid = db.create_user("alice", "s3cret")
    db.create_document_permission("report.pdf", "rag_docs", uid)
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        db.create_document_permission("report.pdf", "rag_docs", uid)


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
