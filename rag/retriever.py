import re

from rank_bm25 import BM25Okapi

from config import settings
from rag.bm25_store import BM25Store
from rag.embedder import embed
from rag.models import Chunk
from rag.vector_store import search as dense_search
from rag.vector_store import search_collection


def _tokenize(text: str) -> list[str]:
    """Tokenize text, using jieba for Chinese and whitespace split for others."""
    if re.search(r"[一-鿿]", text):
        return _chinese_tokenize(text)
    return text.split()


def _chinese_tokenize(text: str) -> list[str]:
    try:
        import jieba

        return list(jieba.cut(text))
    except Exception:
        pass
    # Fallback: character-unigram + known bigrams via sliding window
    tokens: list[str] = []
    buf: list[str] = []
    for ch in text:
        if ch.strip():
            buf.append(ch)
        else:
            if buf:
                tokens.append("".join(buf))
                buf = []
            tokens.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def _load_all_chunks(collection_name: str) -> list[Chunk]:
    """Load all chunks from a Qdrant collection for BM25 indexing.

    NOTE: No read lock is held during the scroll. If concurrent writes occur
    chunks may be added or removed between pages.  This is a known limitation;
    BM25 is rebuilt on each query so any transient inconsistency is ephemeral.
    """
    from rag.vector_store import _get_client

    client = _get_client()
    all_points = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            limit=10000,
            offset=offset,
            with_payload=True,
        )
        all_points.extend(points)
        if offset is None:
            break
    chunks = []
    for point in all_points:
        payload = point.payload or {}
        chunks.append(
            Chunk(
                text=payload.get("text", ""),
                doc_name=payload.get("doc_name", ""),
                chunk_index=payload.get("chunk_index", 0),
            )
        )
    return chunks


class Retriever:
    def __init__(self, chunks: list[Chunk], collection_name: str = None):
        if not chunks and collection_name:
            store = BM25Store()
            if store.has_chunks(collection_name):
                chunks = store.load_chunks(collection_name)
            else:
                chunks = _load_all_chunks(collection_name)
                store.save_chunks(collection_name, chunks)
            store.close()
        self.chunks = chunks
        self.collection_name = collection_name
        if chunks:
            tokenized = [_tokenize(c.text) for c in chunks]
            self.bm25 = BM25Okapi(tokenized)
        else:
            self.bm25 = None

    def retrieve(self, query: str, top_k: int = 5, doc_name: str = None) -> list[Chunk]:
        query_vec = embed([query])[0]
        if self.collection_name:
            dense_hits = search_collection(self.collection_name, query_vec, top_k=top_k * 2, doc_name=doc_name)
        else:
            dense_hits = dense_search(query_vec, top_k=top_k * 2)

        sparse_hits = []
        if self.bm25 is not None and self.chunks:
            tokenized_q = _tokenize(query)
            bm25_scores = self.bm25.get_scores(tokenized_q)
            bm25_indices = sorted(
                range(len(bm25_scores)),
                key=lambda i: bm25_scores[i],
                reverse=True,
            )[: top_k * 2]
            sparse_hits = [self.chunks[i] for i in bm25_indices]

        # 如果指定了文档名，过滤 BM25 结果
        if doc_name:
            sparse_hits = [c for c in sparse_hits if c.doc_name == doc_name]

        return self._rrf_fuse(dense_hits, sparse_hits, top_k, rrf_k=settings.rrf_k)

    @staticmethod
    def _rrf_fuse(dense: list[Chunk], sparse: list[Chunk], top_k: int, rrf_k: int = 60) -> list[Chunk]:
        scores: dict[Chunk, float] = {}
        for rank, doc in enumerate(dense):
            scores[doc] = scores.get(doc, 0) + 1 / (rrf_k + rank + 1)
        for rank, doc in enumerate(sparse):
            scores[doc] = scores.get(doc, 0) + 1 / (rrf_k + rank + 1)
        return sorted(scores, key=lambda d: -scores[d])[:top_k]
