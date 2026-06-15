"""检索空白分析测试。"""
import os
import tempfile


def test_gap_analyzer_creates_table():
    from rag.gap_analyzer import GapAnalyzer
    db_path = tempfile.mktemp(suffix=".db")
    try:
        ga = GapAnalyzer(db_path)
        import sqlite3
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='retrieval_gaps'").fetchall()
        assert len(rows) == 1
        conn.close()
        ga.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_gap_analyzer_records_gap():
    from rag.gap_analyzer import GapAnalyzer
    db_path = tempfile.mktemp(suffix=".db")
    try:
        ga = GapAnalyzer(db_path)
        ga.record_gap("什么是量子计算？", best_score=0.15)
        gaps = ga.get_gaps()
        assert len(gaps) == 1
        assert gaps[0]["question"] == "什么是量子计算？"
        ga.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_gap_analyzer_detects_low_score():
    from rag.gap_analyzer import GapAnalyzer
    assert GapAnalyzer.is_gap(0.15) is True
    assert GapAnalyzer.is_gap(0.5) is False


def test_gap_analyzer_detects_unknown_keywords():
    from rag.gap_analyzer import GapAnalyzer
    assert GapAnalyzer.is_gap(0.8, answer="文档中未找到相关信息") is True
    assert GapAnalyzer.is_gap(0.8, answer="根据文档，答案是...") is False


def test_gap_analyzer_summary():
    from rag.gap_analyzer import GapAnalyzer
    db_path = tempfile.mktemp(suffix=".db")
    try:
        ga = GapAnalyzer(db_path)
        ga.record_gap("问题1", 0.1)
        ga.record_gap("问题2", 0.2)
        ga.record_gap("问题3", 0.1)
        summary = ga.get_summary()
        assert summary["total"] == 3
        assert "top_questions" in summary
        ga.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_gap_analyzer_resolve():
    from rag.gap_analyzer import GapAnalyzer
    db_path = tempfile.mktemp(suffix=".db")
    try:
        ga = GapAnalyzer(db_path)
        ga.record_gap("问题1", 0.1)
        gaps = ga.get_gaps()
        ga.resolve(gaps[0]["id"], "已补充文档")
        gaps_after = ga.get_gaps()
        assert len(gaps_after) == 0  # 已解决的不返回
        ga.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
