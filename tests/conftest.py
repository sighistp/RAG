import pytest


@pytest.fixture(autouse=True)
def reset_vector_store():
    import rag.vector_store as vs
    if vs._client is not None:
        try:
            vs._client.close()
        except Exception:
            pass
    vs._client = None
    # Clear BM25 module-level cache to prevent test pollution
    try:
        import sys
        if "rag.retriever" in sys.modules:
            sys.modules["rag.retriever"]._bm25_cache.clear()
    except Exception:
        pass
    yield
    if vs._client is not None:
        try:
            vs._client.close()
        except Exception:
            pass
    vs._client = None


@pytest.fixture(autouse=True)
def reset_api_pipeline():
    import rag.api
    rag.api.pipeline = None
    yield


@pytest.fixture(autouse=True)
def reset_stream_state():
    """重置流式相关全局状态，防止测试间污染。"""
    import rag.generator as gen
    yield
    gen._async_client = None
    gen._breaker._failure_count = 0
    gen._breaker.state = "closed"
    gen._breaker._probe_admitted = False
