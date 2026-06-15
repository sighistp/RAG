from rag.models import Chunk


def test_chunk_has_text():
    c = Chunk(text="hello", doc_name="test.txt", chunk_index=0)
    assert c.text == "hello"


def test_chunk_has_doc_name():
    c = Chunk(text="hello", doc_name="test.txt", chunk_index=0)
    assert c.doc_name == "test.txt"


def test_chunk_has_index():
    c = Chunk(text="hello", doc_name="test.txt", chunk_index=3)
    assert c.chunk_index == 3
