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
