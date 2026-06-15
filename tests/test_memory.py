"""TDD: Tests for multi-turn dialogue memory."""

from rag.memory import DialogueMemory
from rag.models import Chunk


def test_add_and_get_recent_messages(tmp_path):
    db = tmp_path / "test.db"
    mem = DialogueMemory(str(db))
    mem.add_message("s1", "user", "Hello")
    mem.add_message("s1", "assistant", "Hi there")

    recent = mem.get_recent_messages("s1", n=5)
    assert len(recent) == 2
    assert recent[0].role == "user"
    assert recent[0].content == "Hello"
    assert recent[1].role == "assistant"
    assert recent[1].content == "Hi there"


def test_summary_save_and_get(tmp_path):
    db = tmp_path / "test.db"
    mem = DialogueMemory(str(db))
    assert mem.get_summary("s1") is None
    mem.save_summary("s1", "此前讨论了营收和利润。")
    assert mem.get_summary("s1") == "此前讨论了营收和利润。"


def test_should_summarize(tmp_path):
    db = tmp_path / "test.db"
    mem = DialogueMemory(str(db))
    for i in range(11):
        mem.add_message("s1", "user", f"Q{i}")
        mem.add_message("s1", "assistant", f"A{i}")
    assert mem.should_summarize("s1", max_rounds=10)


def test_summarize_with_mock(tmp_path):
    db = tmp_path / "test.db"
    mem = DialogueMemory(str(db), generate_fn=lambda msgs: "生成摘要")
    for i in range(12):
        mem.add_message("s1", "user", f"Q{i}")
        mem.add_message("s1", "assistant", f"A{i}")
    mem.summarize_old_rounds("s1")
    assert mem.get_summary("s1") == "生成摘要"
    recent = mem.get_recent_messages("s1", n=99)
    assert len(recent) == 24  # 12 rounds kept, not deleted


def test_build_messages_format(tmp_path):
    db = tmp_path / "test.db"
    mem = DialogueMemory(str(db))
    mem.save_summary("s1", "历史：讨论了营收。")
    mem.add_message("s1", "user", "Q1")
    mem.add_message("s1", "assistant", "A1")
    msgs = mem.build_messages("s1", "Q2", ["Context chunk"])
    assert msgs[0]["role"] == "system"
    assert "历史" in msgs[1]["content"]
    assert msgs[1]["role"] == "system"
    assert msgs[2]["role"] == "user" and msgs[2]["content"] == "Q1"
    assert msgs[3]["role"] == "assistant" and msgs[3]["content"] == "A1"
    assert "Context chunk" in msgs[4]["content"]
    assert "Q2" in msgs[4]["content"]


def test_build_messages_no_summary(tmp_path):
    db = tmp_path / "test.db"
    mem = DialogueMemory(str(db))
    msgs = mem.build_messages("s1", "Hello", ["ctx"])
    assert len(msgs) == 2  # system + context+question
    assert msgs[0]["role"] == "system"
    assert "Hello" in msgs[1]["content"]


def test_build_messages_formats_sources(tmp_path):
    db = tmp_path / "test.db"
    mem = DialogueMemory(str(db))
    context = [
        Chunk(text="chunk one", doc_name="doc.md", chunk_index=0),
        Chunk(text="chunk two", doc_name="doc.md", chunk_index=3),
    ]
    msgs = mem.build_messages("s1", "test question", context)

    user_msg = [m for m in msgs if m["role"] == "user"][0]
    content = user_msg["content"]
    assert "[1] doc.md(第1段): chunk one" in content
    assert "[2] doc.md(第4段): chunk two" in content
    assert "问题：test question" in content
