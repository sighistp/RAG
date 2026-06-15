"""检索空白分析 — 记录未解答查询，生成知识缺口报告。"""
import sqlite3
import threading


class GapAnalyzer:
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self):
        with self._lock:
            self._conn.execute("""CREATE TABLE IF NOT EXISTS retrieval_gaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                best_score REAL,
                timestamp TEXT DEFAULT (datetime('now')),
                resolved BOOLEAN DEFAULT FALSE,
                resolution_note TEXT
            )""")
            self._conn.commit()

    @staticmethod
    def is_gap(best_score: float, answer: str = "") -> bool:
        if best_score < 0.3:
            return True
        gap_keywords = ["未找到", "不知道", "文档中未提及", "无法回答", "没有相关信息"]
        return any(kw in answer for kw in gap_keywords)

    def record_gap(self, question: str, best_score: float):
        with self._lock:
            self._conn.execute(
                "INSERT INTO retrieval_gaps (question, best_score) VALUES (?, ?)",
                (question, best_score)
            )
            self._conn.commit()

    def get_gaps(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM retrieval_gaps WHERE resolved = FALSE ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_summary(self) -> dict:
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM retrieval_gaps WHERE resolved = FALSE"
            ).fetchone()[0]
            top = self._conn.execute(
                "SELECT question, COUNT(*) as cnt FROM retrieval_gaps "
                "WHERE resolved = FALSE GROUP BY question ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
        return {"total": total, "top_questions": [{"question": r["question"], "count": r["cnt"]} for r in top]}

    def resolve(self, gap_id: int, note: str = ""):
        with self._lock:
            self._conn.execute(
                "UPDATE retrieval_gaps SET resolved = TRUE, resolution_note = ? WHERE id = ?",
                (note, gap_id)
            )
            self._conn.commit()

    def close(self):
        self._conn.close()
