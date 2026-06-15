from unittest.mock import patch, MagicMock
from qdrant_client.models import Distance, VectorParams
from rag.vector_store import add, search, add_to_collection, search_collection, delete_doc
from rag.models import Chunk


@patch("rag.vector_store.QdrantClient")
def test_add_documents(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.collection_exists.return_value = False

    add([Chunk(text="doc1", doc_name="", chunk_index=0)], [[0.1] * 1024])

    mock_client.create_collection.assert_called_once_with(
        collection_name="rag_docs",
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )
    mock_client.upsert.assert_called_once()


@patch("rag.vector_store.QdrantClient")
def test_search_returns_texts(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.collection_exists.return_value = True

    mock_point = MagicMock()
    mock_point.payload = {"text": "doc content"}
    mock_client.query_points.return_value = MagicMock(points=[mock_point])

    results = search([0.1] * 1024, top_k=3)
    assert isinstance(results[0], Chunk)
    assert results[0].text == "doc content"


@patch("rag.vector_store.QdrantClient")
def test_search_empty(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.collection_exists.return_value = True
    mock_client.query_points.return_value = MagicMock(points=[])

    results = search([0.1] * 1024, top_k=3)
    assert results == []


@patch("rag.vector_store.QdrantClient")
def test_add_stores_chunk_metadata(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.collection_exists.return_value = True

    chunks = [Chunk(text="doc1", doc_name="test.txt", chunk_index=0)]
    add(chunks, [[0.1] * 1024])

    call_args = mock_client.upsert.call_args
    point = call_args.kwargs["points"][0]
    assert point.payload["text"] == "doc1"
    assert point.payload["doc_name"] == "test.txt"
    assert point.payload["chunk_index"] == 0


@patch("rag.vector_store.QdrantClient")
def test_search_returns_chunks(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.collection_exists.return_value = True

    mock_point = MagicMock()
    mock_point.payload = {"text": "doc content", "doc_name": "test.txt", "chunk_index": 2}
    mock_client.query_points.return_value = MagicMock(points=[mock_point])

    results = search([0.1] * 1024, top_k=3)
    assert len(results) == 1
    assert isinstance(results[0], Chunk)
    assert results[0].text == "doc content"
    assert results[0].doc_name == "test.txt"
    assert results[0].chunk_index == 2


@patch("rag.vector_store.QdrantClient")
def test_add_to_collection(mock_client_class):
    """add_to_collection should add chunks to a specific collection."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.collection_exists.return_value = True

    chunks = [Chunk(text="doc1", doc_name="test.txt", chunk_index=0)]
    add_to_collection("my_kb", chunks, [[0.1] * 1024])

    mock_client.upsert.assert_called_once()
    call_args = mock_client.upsert.call_args
    assert call_args.kwargs["collection_name"] == "my_kb"


@patch("rag.vector_store.QdrantClient")
def test_add_to_collection_raises_if_not_exists(mock_client_class):
    """add_to_collection should raise ValueError if collection doesn't exist."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.collection_exists.return_value = False

    chunks = [Chunk(text="doc1", doc_name="test.txt", chunk_index=0)]
    import pytest
    with pytest.raises(ValueError, match="不存在"):
        add_to_collection("new_kb", chunks, [[0.1] * 1024])


@patch("rag.vector_store.QdrantClient")
def test_search_collection(mock_client_class):
    """search_collection should search from a specific collection."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.collection_exists.return_value = True

    mock_point = MagicMock()
    mock_point.payload = {"text": "doc content", "doc_name": "test.txt", "chunk_index": 0}
    mock_client.query_points.return_value = MagicMock(points=[mock_point])

    results = search_collection("my_kb", [0.1] * 1024, top_k=3)

    assert len(results) == 1
    assert results[0].text == "doc content"
    mock_client.query_points.assert_called_once()
    call_args = mock_client.query_points.call_args
    assert call_args.kwargs["collection_name"] == "my_kb"


@patch("rag.vector_store.QdrantClient")
def test_search_collection_empty(mock_client_class):
    """search_collection should return empty list when no results."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.collection_exists.return_value = True
    mock_client.query_points.return_value = MagicMock(points=[])

    results = search_collection("my_kb", [0.1] * 1024)
    assert results == []


@patch("rag.vector_store.QdrantClient")
def test_delete_doc(mock_client_class):
    """delete_doc should delete documents by doc_name from a collection."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    delete_doc("my_kb", "test.txt")

    mock_client.delete.assert_called_once()
    call_args = mock_client.delete.call_args
    assert call_args.kwargs["collection_name"] == "my_kb"
