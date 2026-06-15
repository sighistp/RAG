from rag.chunker import chunk
from rag.models import Chunk


def test_chunk_empty():
    assert chunk("") == []


def test_chunk_short_text():
    result = chunk("hello world", chunk_size=500, overlap=80)
    assert result[0].text == "hello world"


def test_chunk_long_text():
    text = "A" * 1200
    result = chunk(text, chunk_size=500, overlap=80)
    assert len(result) >= 2
    for c in result:
        assert len(c.text) <= 500


def test_chunk_chinese():
    text = "你好世界，" * 200
    result = chunk(text, chunk_size=200, overlap=30)
    assert len(result) >= 2


def test_chunk_returns_chunk_objects():
    result = chunk("hello world", doc_name="test.txt")
    assert len(result) == 1
    assert isinstance(result[0], Chunk)
    assert result[0].text == "hello world"
    assert result[0].doc_name == "test.txt"
    assert result[0].chunk_index == 0


def test_chunk_multiple_has_sequential_indices():
    text = "A" * 1200
    result = chunk(text, doc_name="doc.md", chunk_size=500, overlap=80)
    assert len(result) >= 2
    for i, c in enumerate(result):
        assert c.chunk_index == i
        assert c.doc_name == "doc.md"
