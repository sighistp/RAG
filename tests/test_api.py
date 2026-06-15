from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from rag.api import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "components" in data


@patch("rag.api.KnowledgeBaseManager")
def test_index_adds_to_kb(mock_kb_cls, tmp_path):
    mock_manager = MagicMock()
    mock_manager.add_document.return_value = 5
    mock_kb_cls.return_value = mock_manager

    doc = tmp_path / "test.txt"
    doc.write_text("test content")

    with open(doc, "rb") as f:
        response = client.post("/index", files={"file": ("test.txt", f, "text/plain")})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "indexed"
    assert data["chunks"] == 5
    mock_manager.add_document.assert_called_once()


@patch("rag.pipeline.RAGPipeline")
def test_query_without_index_returns_400(mock_pipeline_cls):
    response = client.post("/query", json={"question": "test"})
    assert response.status_code == 400


def test_query_returns_answer():
    import rag.api as api_module
    mock_pipeline = MagicMock()
    mock_pipeline.query.return_value = MagicMock(answer="answer from RAG", sources=[])

    # 直接设置全局 pipeline
    api_module.pipeline = mock_pipeline
    try:
        response = client.post("/query", json={"question": "what is RAG?"})
        assert response.status_code == 200
        assert response.json()["answer"] == "answer from RAG"
    finally:
        api_module.pipeline = None


@patch("rag.api.KnowledgeBaseManager")
def test_query_knowledge_base(mock_kb_manager_cls):
    """POST /knowledge-bases/{kb_id}/query should return search results."""
    from rag.models import Chunk

    mock_manager = MagicMock()
    mock_manager.search.return_value = [
        Chunk(text="RAG is retrieval augmented generation", doc_name="doc.txt", chunk_index=0),
    ]
    mock_kb_manager_cls.return_value = mock_manager

    response = client.post(
        "/knowledge-bases/kb_abc12345/query",
        json={"question": "what is RAG?", "top_k": 3},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["kb_id"] == "kb_abc12345"
    assert len(data["results"]) == 1
    assert data["results"][0]["doc_name"] == "doc.txt"
    mock_manager.search.assert_called_once_with("kb_abc12345", "what is RAG?", top_k=3)


@patch("rag.api.KnowledgeBaseManager")
def test_delete_system_collection_returns_400(mock_kb_manager_cls):
    """DELETE /knowledge-bases/rag_docs should return 400 (bad request)."""
    mock_manager = MagicMock()
    mock_manager.delete_kb.side_effect = ValueError("不能删除系统集合 rag_docs，只能删除 kb_ 前缀的知识库")
    mock_kb_manager_cls.return_value = mock_manager

    response = client.delete("/knowledge-bases/rag_docs")

    assert response.status_code == 400
    assert "不能删除" in response.json()["detail"]


def test_health_returns_component_status():
    """GET /health should return component status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "components" in data
