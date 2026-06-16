"""TDD tests for UserDB data_sources table operations."""

import pytest

from rag.user_db import UserDB


@pytest.fixture()
def db(tmp_path):
    """Yield a fresh UserDB backed by a temporary SQLite file."""
    path = str(tmp_path / "test.db")
    udb = UserDB(path)
    yield udb
    udb.close()


# ── Create ───────────────────────────────────────────────────────────────────


class TestCreateDataSource:
    def test_create_source(self, db):
        source_id = db.create_data_source(
            name="My Feed",
            source_type="rss",
            config='{"url": "https://example.com/feed.xml"}',
        )
        assert isinstance(source_id, int)
        assert source_id > 0

    def test_create_source_returns_config(self, db):
        source_id = db.create_data_source(
            name="Test",
            source_type="database",
            config='{"connection_string": "sqlite:///test.db", "query": "SELECT 1"}',
        )
        assert source_id > 0


# ── List ─────────────────────────────────────────────────────────────────────


class TestListDataSources:
    def test_list_empty(self, db):
        sources = db.list_data_sources()
        assert sources == []

    def test_list_after_create(self, db):
        db.create_data_source(name="A", source_type="rss", config="{}")
        db.create_data_source(name="B", source_type="api", config="{}")
        sources = db.list_data_sources()
        assert len(sources) == 2
        names = {s["name"] for s in sources}
        assert names == {"A", "B"}

    def test_list_fields(self, db):
        db.create_data_source(name="X", source_type="rss", config='{"url": "http://x"}')
        sources = db.list_data_sources()
        s = sources[0]
        assert "id" in s
        assert s["name"] == "X"
        assert s["type"] == "rss"
        assert "config" in s
        assert s["status"] == "inactive"
        assert "last_synced_at" in s
        assert "created_at" in s


# ── Get by ID ────────────────────────────────────────────────────────────────


class TestGetDataSource:
    def test_get_existing(self, db):
        sid = db.create_data_source(name="G", source_type="rss", config="{}")
        source = db.get_data_source(sid)
        assert source is not None
        assert source["name"] == "G"

    def test_get_nonexistent(self, db):
        source = db.get_data_source(99999)
        assert source is None


# ── Delete ───────────────────────────────────────────────────────────────────


class TestDeleteDataSource:
    def test_delete_existing(self, db):
        sid = db.create_data_source(name="D", source_type="rss", config="{}")
        assert db.delete_data_source(sid) is True
        assert db.get_data_source(sid) is None

    def test_delete_nonexistent(self, db):
        assert db.delete_data_source(99999) is False

    def test_list_after_delete(self, db):
        sid = db.create_data_source(name="D", source_type="rss", config="{}")
        db.create_data_source(name="K", source_type="api", config="{}")
        db.delete_data_source(sid)
        sources = db.list_data_sources()
        assert len(sources) == 1
        assert sources[0]["name"] == "K"


# ── Update last_synced_at ───────────────────────────────────────────────────


class TestUpdateLastSynced:
    def test_update_last_synced(self, db):
        sid = db.create_data_source(name="S", source_type="rss", config="{}")
        source = db.get_data_source(sid)
        assert source["last_synced_at"] is None

        db.update_data_source_synced(sid)
        source = db.get_data_source(sid)
        assert source["last_synced_at"] is not None

    def test_update_status(self, db):
        sid = db.create_data_source(name="S", source_type="rss", config="{}")
        db.update_data_source_status(sid, "active")
        source = db.get_data_source(sid)
        assert source["status"] == "active"
