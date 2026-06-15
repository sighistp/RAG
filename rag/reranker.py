"""Re-ranking module using Bailian Rerank API."""

import logging

import requests

from config import settings
from rag.models import Chunk
from rag.resilience import CircuitBreaker, retry

logger = logging.getLogger(__name__)

_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)


class Reranker:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = requests.Session()
            self._client.headers.update(
                {
                    "Authorization": f"Bearer {settings.bailian_api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._client

    @retry(
        max_attempts=3,
        backoff_base=1.0,
        retryable_exceptions=(requests.RequestException, TimeoutError, ConnectionError),
    )
    def _call_rerank_api(self, query: str, texts: list[str], top_k: int) -> list[dict]:
        client = self._get_client()
        url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        payload = {
            "model": settings.bailian_rerank_model,
            "input": {
                "query": query,
                "documents": texts,
            },
            "parameters": {
                "top_n": top_k,
            },
        }
        resp = client.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        try:
            return resp.json()["output"]["results"]
        except (KeyError, TypeError) as e:
            raise RuntimeError(f"Unexpected rerank API response: {e}") from e

    def rerank(self, query: str, documents: list[Chunk], top_k: int | None = None) -> list[Chunk]:
        if not documents:
            return []
        if top_k is None:
            top_k = settings.rerank_top_k
        if not _breaker.allow_request():
            logger.warning("Circuit breaker open — falling back to original document order")
            return documents[:top_k]
        texts = [c.text for c in documents]
        try:
            results = self._call_rerank_api(query, texts, min(top_k, len(documents)))
            _breaker.record_success()
            indexed = {i: documents[i] for i in range(len(documents))}
            return [indexed[r["index"]] for r in sorted(results, key=lambda x: -x["relevance_score"])][:top_k]
        except Exception:
            _breaker.record_failure()
            logger.warning("Rerank failed — falling back to original document order", exc_info=True)
            return documents[:top_k]
