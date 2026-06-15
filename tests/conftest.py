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
