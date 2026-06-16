"""Tests for analysis cards (DB + API) and conversation mode."""

import pytest
from fastapi.testclient import TestClient

from rag.user_db import UserDB


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path):
    """Yield a fresh UserDB backed by a temporary SQLite file."""
    path = str(tmp_path / "test.db")
    udb = UserDB(path)
    yield udb
    udb.close()


@pytest.fixture()
def client(tmp_path):
    """Yield a TestClient with a temporary UserDB patched in."""
    db_path = str(tmp_path / "test_users.db")
    import rag.api as api_mod

    original_db = api_mod.user_db
    api_mod.user_db = UserDB(db_path)
    with TestClient(api_mod.app) as c:
        yield c
    api_mod.user_db = original_db


def _register_and_login(client, username="analysis_user", password="pass123456"):
    """Helper: register a user and return the JWT token."""
    client.post("/register", json={"username": username, "password": password})
    resp = client.post("/login", json={"username": username, "password": password})
    return resp.json()["token"]


# ═══════════════════════════════════════════════════════════════════════════
# Part 1: Database-level tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAnalysisCardsDB:
    """Test analysis_cards and analysis_questions CRUD via UserDB directly."""

    def test_tables_exist(self, db):
        """Both analysis_cards and analysis_questions tables should exist."""
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "analysis_cards" in tables
        assert "analysis_questions" in tables

    def test_create_card(self, db):
        uid = db.create_user("alice", "s3cret")
        card_id = db.create_card(uid, "My Analysis")
        assert isinstance(card_id, int) and card_id > 0

    def test_list_cards(self, db):
        uid = db.create_user("alice", "s3cret")
        db.create_card(uid, "Card A")
        db.create_card(uid, "Card B")
        cards = db.list_cards(uid)
        assert len(cards) == 2
        names = {c["name"] for c in cards}
        assert names == {"Card A", "Card B"}

    def test_list_cards_by_user(self, db):
        """Cards from user2 should not appear in user1's list."""
        uid1 = db.create_user("alice", "s3cret")
        uid2 = db.create_user("bob", "s3cret")
        db.create_card(uid1, "Alice Card")
        db.create_card(uid2, "Bob Card")
        cards = db.list_cards(uid1)
        assert len(cards) == 1
        assert cards[0]["name"] == "Alice Card"

    def test_delete_card(self, db):
        uid = db.create_user("alice", "s3cret")
        card_id = db.create_card(uid, "Temp Card")
        assert db.delete_card(card_id) is True
        assert db.list_cards(uid) == []

    def test_delete_card_cascades_questions(self, db):
        uid = db.create_user("alice", "s3cret")
        card_id = db.create_card(uid, "Temp Card")
        db.add_question(card_id, "What is X?")
        db.add_question(card_id, "What is Y?")
        assert db.delete_card(card_id) is True
        assert db.list_cards(uid) == []

    def test_rename_card(self, db):
        uid = db.create_user("alice", "s3cret")
        card_id = db.create_card(uid, "Old Name")
        assert db.rename_card(card_id, "New Name") is True
        cards = db.list_cards(uid)
        assert cards[0]["name"] == "New Name"

    def test_rename_card_nonexistent(self, db):
        assert db.rename_card(9999, "New") is False

    def test_add_question(self, db):
        uid = db.create_user("alice", "s3cret")
        card_id = db.create_card(uid, "Card")
        qid = db.add_question(card_id, "What is AI?")
        assert isinstance(qid, int) and qid > 0

    def test_add_question_with_defaults(self, db):
        uid = db.create_user("alice", "s3cret")
        card_id = db.create_card(uid, "Card")
        qid = db.add_question(card_id, "What is ML?")
        questions = db.get_questions(card_id)
        assert len(questions) == 1
        q = questions[0]
        assert q["id"] == qid
        assert q["question"] == "What is ML?"
        assert q["answer"] == ""
        assert q["source_mode"] == ""
        assert q["source_message_id"] is None

    def test_add_question_with_all_fields(self, db):
        uid = db.create_user("alice", "s3cret")
        card_id = db.create_card(uid, "Card")
        qid = db.add_question(
            card_id,
            "What is RAG?",
            answer="Retrieval-Augmented Generation",
            source_mode="chat",
            source_message_id=42,
        )
        questions = db.get_questions(card_id)
        assert len(questions) == 1
        q = questions[0]
        assert q["answer"] == "Retrieval-Augmented Generation"
        assert q["source_mode"] == "chat"
        assert q["source_message_id"] == 42

    def test_get_questions_empty(self, db):
        uid = db.create_user("alice", "s3cret")
        card_id = db.create_card(uid, "Card")
        assert db.get_questions(card_id) == []

    def test_get_questions_ordered(self, db):
        uid = db.create_user("alice", "s3cret")
        card_id = db.create_card(uid, "Card")
        db.add_question(card_id, "Q2")
        db.add_question(card_id, "Q1")
        questions = db.get_questions(card_id)
        assert len(questions) == 2

    def test_delete_question(self, db):
        uid = db.create_user("alice", "s3cret")
        card_id = db.create_card(uid, "Card")
        qid = db.add_question(card_id, "What?")
        assert db.delete_question(qid) is True
        assert db.get_questions(card_id) == []

    def test_delete_question_nonexistent(self, db):
        assert db.delete_question(9999) is False


# ═══════════════════════════════════════════════════════════════════════════
# Part 2: API-level tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAnalysisCardsAPI:
    """Test analysis card API endpoints with JWT auth."""

    def test_create_card(self, client):
        token = _register_and_login(client, "api_create", "pass123456")
        resp = client.post(
            "/analysis/cards",
            json={"name": "My Analysis"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["name"] == "My Analysis"

    def test_list_cards(self, client):
        token = _register_and_login(client, "api_list", "pass123456")
        client.post(
            "/analysis/cards",
            json={"name": "Card A"},
            headers={"Authorization": f"Bearer {token}"},
        )
        client.post(
            "/analysis/cards",
            json={"name": "Card B"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.get(
            "/analysis/cards",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_delete_card(self, client):
        token = _register_and_login(client, "api_delete", "pass123456")
        create_resp = client.post(
            "/analysis/cards",
            json={"name": "Temp"},
            headers={"Authorization": f"Bearer {token}"},
        )
        card_id = create_resp.json()["id"]
        resp = client.delete(
            f"/analysis/cards/{card_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_card_not_found(self, client):
        token = _register_and_login(client, "api_del_nf", "pass123456")
        resp = client.delete(
            "/analysis/cards/9999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_rename_card(self, client):
        token = _register_and_login(client, "api_rename", "pass123456")
        create_resp = client.post(
            "/analysis/cards",
            json={"name": "Old"},
            headers={"Authorization": f"Bearer {token}"},
        )
        card_id = create_resp.json()["id"]
        resp = client.put(
            f"/analysis/cards/{card_id}/name",
            json={"name": "New"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    def test_add_question(self, client):
        token = _register_and_login(client, "api_addq", "pass123456")
        create_resp = client.post(
            "/analysis/cards",
            json={"name": "Card"},
            headers={"Authorization": f"Bearer {token}"},
        )
        card_id = create_resp.json()["id"]
        resp = client.post(
            f"/analysis/cards/{card_id}/questions",
            json={"question": "What is AI?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["question"] == "What is AI?"

    def test_delete_question(self, client):
        token = _register_and_login(client, "api_delq", "pass123456")
        create_resp = client.post(
            "/analysis/cards",
            json={"name": "Card"},
            headers={"Authorization": f"Bearer {token}"},
        )
        card_id = create_resp.json()["id"]
        add_resp = client.post(
            f"/analysis/cards/{card_id}/questions",
            json={"question": "What?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        qid = add_resp.json()["id"]
        resp = client.delete(
            f"/analysis/cards/{card_id}/questions/{qid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_unauthorized_create_card(self, client):
        resp = client.post("/analysis/cards", json={"name": "X"})
        assert resp.status_code in (401, 403, 422)

    def test_unauthorized_list_cards(self, client):
        resp = client.get("/analysis/cards")
        assert resp.status_code in (401, 403, 422)


# ═══════════════════════════════════════════════════════════════════════════
# Part 3: Conversation mode tests
# ═══════════════════════════════════════════════════════════════════════════


class TestConversationModeDB:
    """Test conversation mode field at the DB level."""

    def test_conversation_has_mode_column(self, db):
        """conversations table should have a mode column."""
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        cursor = conn.execute("PRAGMA table_info(conversations)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "mode" in columns

    def test_create_conversation_default_mode(self, db):
        uid = db.create_user("alice", "s3cret")
        cid = db.create_conversation(uid, "Chat")
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        row = conn.execute("SELECT mode FROM conversations WHERE id = ?", (cid,)).fetchone()
        conn.close()
        assert row[0] == "file"

    def test_create_conversation_with_mode(self, db):
        uid = db.create_user("alice", "s3cret")
        cid = db.create_conversation(uid, "Chat", mode="chat")
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        row = conn.execute("SELECT mode FROM conversations WHERE id = ?", (cid,)).fetchone()
        conn.close()
        assert row[0] == "chat"

    def test_list_conversations_filter_by_mode(self, db):
        uid = db.create_user("alice", "s3cret")
        db.create_conversation(uid, "File Chat", mode="file")
        db.create_conversation(uid, "Analysis Chat", mode="analysis")
        db.create_conversation(uid, "Another File", mode="file")

        all_convs = db.list_conversations(uid)
        assert len(all_convs) == 3

        file_convs = db.list_conversations(uid, mode="file")
        assert len(file_convs) == 2

        analysis_convs = db.list_conversations(uid, mode="analysis")
        assert len(analysis_convs) == 1


class TestConversationModeAPI:
    """Test conversation mode at the API level."""

    def test_create_conversation_with_mode(self, client):
        token = _register_and_login(client, "mode_create", "pass123456")
        resp = client.post(
            "/conversations",
            json={"mode": "analysis"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "analysis"

    def test_create_conversation_default_mode(self, client):
        token = _register_and_login(client, "mode_default", "pass123456")
        resp = client.post(
            "/conversations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["mode"] == "file"

    def test_list_conversations_with_mode_filter(self, client):
        token = _register_and_login(client, "mode_list", "pass123456")
        # Create conversations with different modes
        client.post(
            "/conversations",
            json={"mode": "file"},
            headers={"Authorization": f"Bearer {token}"},
        )
        client.post(
            "/conversations",
            json={"mode": "analysis"},
            headers={"Authorization": f"Bearer {token}"},
        )
        client.post(
            "/conversations",
            json={"mode": "file"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # List all
        resp = client.get(
            "/conversations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 3

        # Filter by mode=file
        resp = client.get(
            "/conversations?mode=file",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        # Filter by mode=analysis
        resp = client.get(
            "/conversations?mode=analysis",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
