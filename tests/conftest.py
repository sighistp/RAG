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
