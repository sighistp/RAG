"""Tests for /register and /login API endpoints."""

import pytest
from fastapi.testclient import TestClient

from rag.user_db import UserDB


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


def test_register(client):
    """POST /register with valid data returns 200 and a token."""
    resp = client.post("/register", json={"username": "alice", "password": "Secret123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["username"] == "alice"


def test_register_duplicate(client):
    """Registering the same username twice returns 400."""
    client.post("/register", json={"username": "bob", "password": "Secret123"})
    resp = client.post("/register", json={"username": "bob", "password": "Secret123"})
    assert resp.status_code == 400


def test_login(client):
    """Register then login returns 200 and a token."""
    client.post("/register", json={"username": "charlie", "password": "Secret123"})
    resp = client.post("/login", json={"username": "charlie", "password": "Secret123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["username"] == "charlie"


def test_login_wrong_password(client):
    """Login with wrong password returns 401."""
    client.post("/register", json={"username": "dave", "password": "Secret123"})
    resp = client.post("/login", json={"username": "dave", "password": "wrongpassword"})
    assert resp.status_code == 401
