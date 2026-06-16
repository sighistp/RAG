"""SQLite-backed user database for conversations, messages, and feedback."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
from typing import Any


class UserDB:
    """Thread-safe SQLite database for users, conversations, messages, and feedback."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    username    TEXT    NOT NULL UNIQUE,
                    salt        TEXT    NOT NULL,
                    password    TEXT    NOT NULL,
                    created_at  REAL    NOT NULL DEFAULT (strftime('%s','now'))
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL REFERENCES users(id),
                    title       TEXT    NOT NULL DEFAULT '',
                    created_at  REAL    NOT NULL DEFAULT (strftime('%s','now'))
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                    role            TEXT    NOT NULL,
                    content         TEXT    NOT NULL,
                    created_at      REAL    NOT NULL DEFAULT (strftime('%s','now'))
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id  INTEGER NOT NULL REFERENCES chat_messages(id),
                    user_id     INTEGER NOT NULL REFERENCES users(id),
                    value       INTEGER NOT NULL,
                    comment     TEXT    NOT NULL DEFAULT '',
                    created_at  REAL    NOT NULL DEFAULT (strftime('%s','now')),
                    UNIQUE(message_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS kb_metadata (
                    kb_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    overview TEXT DEFAULT '',
                    user_id INTEGER,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS kb_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kb_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT,
                    toc TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    chunk_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    added_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(kb_id, filename)
                );

                CREATE TABLE IF NOT EXISTS data_sources (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    name            TEXT    NOT NULL,
                    type            TEXT    NOT NULL,
                    config          TEXT    NOT NULL DEFAULT '{}',
                    status          TEXT    NOT NULL DEFAULT 'inactive',
                    last_synced_at  REAL,
                    created_at      REAL    NOT NULL DEFAULT (strftime('%s','now'))
                );
                """
            )

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def create_user(self, username: str, password: str) -> int:
        """Create a new user.  Raises ``ValueError`` if the username is taken."""
        from rag.auth import hash_password

        hashed = hash_password(password)
        with self._lock:
            try:
                cur = self._conn.execute(
                    "INSERT INTO users (username, salt, password) VALUES (?, ?, ?)",
                    (username, "", hashed),
                )
                self._conn.commit()
                return cur.lastrowid  # type: ignore[return-value]
            except sqlite3.IntegrityError:
                raise ValueError(f"Username '{username}' already exists")

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        """Return user dict on success, ``None`` on failure."""
        from rag.auth import verify_password

        with self._lock:
            row = self._conn.execute(
                "SELECT id, username, password FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if row is None:
            return None
        if not verify_password(password, row["password"]):
            return None
        return {"id": row["id"], "username": row["username"]}

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        """Return user dict or ``None``."""
        with self._lock:
            row = self._conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "username": row["username"]}

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def create_conversation(self, user_id: int, title: str = "") -> int:
        """Create a conversation and return its id."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
                (user_id, title),
            )
            self._conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def list_conversations(self, user_id: int) -> list[dict[str, Any]]:
        """Return all conversations for *user_id*, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, user_id, title, created_at FROM conversations WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Delete a conversation (only if owned by user_id). Returns True if deleted."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM chat_messages WHERE conversation_id = ? "
                "AND conversation_id IN (SELECT id FROM conversations WHERE id = ? AND user_id = ?)",
                (conversation_id, conversation_id, user_id),
            )
            cur = self._conn.execute(
                "DELETE FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def add_message(self, conversation_id: int, role: str, content: str) -> int:
        """Append a message to a conversation and return its id."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO chat_messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, role, content),
            )
            self._conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def get_messages(self, conversation_id: int, user_id: int) -> list[dict[str, Any]]:
        """Return all messages in a conversation (only if owned by user_id)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT m.id, m.conversation_id, m.role, m.content, m.created_at "
                "FROM chat_messages m "
                "JOIN conversations c ON m.conversation_id = c.id "
                "WHERE m.conversation_id = ? AND c.user_id = ? ORDER BY m.created_at",
                (conversation_id, user_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_message(self, message_id: int, new_content: str, user_id: int = None):
        """更新消息内容（用于重新生成）。可选 user_id 校验所有权。"""
        with self._lock:
            if user_id is not None:
                # Verify the message belongs to a conversation owned by this user
                self._conn.execute(
                    "UPDATE chat_messages SET content = ? WHERE id = ? "
                    "AND conversation_id IN (SELECT id FROM conversations WHERE user_id = ?)",
                    (new_content, message_id, user_id),
                )
            else:
                self._conn.execute(
                    "UPDATE chat_messages SET content = ? WHERE id = ?",
                    (new_content, message_id),
                )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    def add_feedback(
        self,
        message_id: int,
        user_id: int,
        value: int,
        comment: str = "",
    ) -> int:
        """Record user feedback on a message and return feedback id."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR REPLACE INTO feedback (message_id, user_id, value, comment) VALUES (?, ?, ?, ?)",
                (message_id, user_id, value, comment),
            )
            self._conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def message_belongs_to_user(self, message_id: int, user_id: int) -> bool:
        """Check if a message belongs to a conversation owned by user_id."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM chat_messages m "
                "JOIN conversations c ON m.conversation_id = c.id "
                "WHERE m.id = ? AND c.user_id = ?",
                (message_id, user_id),
            ).fetchone()
        return row is not None

    # ------------------------------------------------------------------
    # Data Sources
    # ------------------------------------------------------------------

    def create_data_source(self, name: str, source_type: str, config: str) -> int:
        """Create a data source and return its id."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO data_sources (name, type, config) VALUES (?, ?, ?)",
                (name, source_type, config),
            )
            self._conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def list_data_sources(self) -> list[dict[str, Any]]:
        """Return all data sources, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, name, type, config, status, last_synced_at, created_at "
                "FROM data_sources ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_data_source(self, source_id: int) -> dict[str, Any] | None:
        """Return a single data source by id, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id, name, type, config, status, last_synced_at, created_at "
                "FROM data_sources WHERE id = ?",
                (source_id,),
            ).fetchone()
        return dict(row) if row else None

    def delete_data_source(self, source_id: int) -> bool:
        """Delete a data source.  Returns True if deleted."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM data_sources WHERE id = ?",
                (source_id,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def update_data_source_synced(self, source_id: int) -> None:
        """Update the last_synced_at timestamp to now."""
        import time

        with self._lock:
            self._conn.execute(
                "UPDATE data_sources SET last_synced_at = ? WHERE id = ?",
                (time.time(), source_id),
            )
            self._conn.commit()

    def update_data_source_status(self, source_id: int, status: str) -> None:
        """Update the status of a data source."""
        with self._lock:
            self._conn.execute(
                "UPDATE data_sources SET status = ? WHERE id = ?",
                (status, source_id),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            self._conn.close()
