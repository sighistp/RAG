"""反馈驱动检索优化 — chunk 级别权重管理。"""
import sqlite3
import threading


class FeedbackProcessor:
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self):
        with self._lock:
            self._conn.execute("""CREATE TABLE IF NOT EXISTS chunk_feedback (
                chunk_hash TEXT PRIMARY KEY,
                weight REAL DEFAULT 1.0,
                positive_count INTEGER DEFAULT 0,
                negative_count INTEGER DEFAULT 0,
                last_updated TEXT DEFAULT (datetime('now'))
            )""")
            self._conn.execute("""CREATE TABLE IF NOT EXISTS feedback_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_hash TEXT NOT NULL,
                user_id INTEGER,
                value TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now'))
            )""")
            self._conn.commit()

    def record_feedback(self, chunk_hash: str, value: str, user_id: int = None):
        with self._lock:
            if user_id is not None:
                existing = self._conn.execute(
                    "SELECT id FROM feedback_log WHERE chunk_hash = ? AND user_id = ?",
                    (chunk_hash, user_id)
                ).fetchone()
                if existing:
                    return
            self._conn.execute(
                "INSERT INTO feedback_log (chunk_hash, user_id, value) VALUES (?, ?, ?)",
                (chunk_hash, user_id, value)
            )
            self._conn.execute(
                "INSERT INTO chunk_feedback (chunk_hash, weight, positive_count, negative_count) "
                "VALUES (?, 1.0, 0, 0) ON CONFLICT(chunk_hash) DO NOTHING",
                (chunk_hash,)
            )
            if value == "negative":
                self._conn.execute(
                    "UPDATE chunk_feedback SET weight = MAX(0.2, weight - 0.1), "
                    "negative_count = negative_count + 1, last_updated = datetime('now') "
                    "WHERE chunk_hash = ?", (chunk_hash,)
                )
            elif value == "positive":
                self._conn.execute(
                    "UPDATE chunk_feedback SET weight = MIN(2.0, weight + 0.1), "
                    "positive_count = positive_count + 1, last_updated = datetime('now') "
                    "WHERE chunk_hash = ?", (chunk_hash,)
                )
            self._conn.commit()

    def get_weight(self, chunk_hash: str) -> float:
        with self._lock:
            row = self._conn.execute(
                "SELECT weight FROM chunk_feedback WHERE chunk_hash = ?", (chunk_hash,)
            ).fetchone()
        return row[0] if row else 1.0

    def get_weights(self, chunk_hashes: list[str]) -> dict[str, float]:
        if not chunk_hashes:
            return {}
        with self._lock:
            placeholders = ",".join("?" * len(chunk_hashes))
            rows = self._conn.execute(
                f"SELECT chunk_hash, weight FROM chunk_feedback WHERE chunk_hash IN ({placeholders})",
                chunk_hashes
            ).fetchall()
        result = {h: 1.0 for h in chunk_hashes}
        for row in rows:
            result[row[0]] = row[1]
        return result

    def decay_weights(self):
        with self._lock:
            self._conn.execute(
                "UPDATE chunk_feedback SET weight = 1.0 + (weight - 1.0) * 0.95, "
                "last_updated = datetime('now')"
            )
            self._conn.commit()

    def close(self):
        self._conn.close()
