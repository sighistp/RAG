import logging
import threading
import time
from typing import NamedTuple

from config import settings
from rag.chunker import chunk
from rag.cleaner import clean_document, deduplicate_chunks
from rag.embedder import embed
from rag.generator import generate
from rag.guard import check_injection, check_output, sanitize_input
from rag.loader import load
from rag.models import Chunk
from rag.query_rewriter import rewrite_query
from rag.reranker import Reranker
from rag.resilience import ResultCache
from rag.retriever import Retriever
from rag.tracker import ExecutionTrace, ExecutionTracker, ToolCall
from rag.vector_store import add, clear

logger = logging.getLogger(__name__)


class QueryResult(NamedTuple):
    answer: str
    context: list[Chunk]
    sources: list[dict]


class RAGPipeline:
    def __init__(
        self, file_path: str = None, session_id: str = None, memory_db_path: str = settings.memory_db_path, kb_id: str = None
    ):
        if kb_id:
            # 查询已有知识库，不重新索引
            self.chunks = []
            self.retriever = Retriever(self.chunks, collection_name=kb_id)
        else:
            # 索引新文档到默认集合
            text = load(file_path)
            text, _metadata = clean_document(text)
            doc_name = file_path.split("/")[-1].split("\\")[-1]
            self.chunks = chunk(text, doc_name=doc_name)
            # 去重（SequenceMatcher 相似度 > 0.95 的段落被去除）
            chunk_texts = [c.text for c in self.chunks]
            unique_texts = deduplicate_chunks(chunk_texts)
            if len(unique_texts) < len(chunk_texts):
                unique_set = set(unique_texts)
                self.chunks = [c for c in self.chunks if c.text in unique_set]
            embeddings = embed([c.text for c in self.chunks])
            clear()
            add(self.chunks, embeddings)
            self.retriever = Retriever(self.chunks)
        self.session_id = session_id or file_path
        from rag.memory import DialogueMemory

        self.memory = DialogueMemory(db_path=memory_db_path, generate_fn=generate)
        self.reranker = Reranker()
        from rag.agent import RAGAgent

        self.agent = RAGAgent(retriever=self.retriever)
        self.tracker = ExecutionTracker(db_path=memory_db_path)
        self._cache = ResultCache()
        self._agent_lock = threading.Lock()

    def _prepare_context(self, question: str, session_id: str, doc_name: str, top_k: int = 8):
        """公共逻辑：guard -> cache -> route -> retrieve -> rerank -> build_messages。"""
        question = sanitize_input(question)
        guard = check_injection(question)
        if guard.blocked:
            return None, f"请求被安全策略拦截：{guard.reason}"

        cached = self._cache.get(question)
        if cached:
            return {"route": "cached", "answer": cached, "context": [], "sources": [{"doc_name": "缓存", "chunk_index": 0}]}, None

        from rag.agent import route_question
        route = route_question(question)

        if route == "agent":
            return {"route": "agent", "question": question}, None

        rewritten = rewrite_query(question)
        context = self.retriever.retrieve(rewritten, top_k=top_k, doc_name=doc_name)
        context = self.reranker.rerank(rewritten, context)
        sid = session_id or self.session_id or "default"
        messages = self.memory.build_messages(sid, question, context)
        sources = [
            {"doc_name": c.doc_name, "chunk_index": c.chunk_index, "text_preview": c.text[:100]} for c in context
        ]
        return {"route": "rag", "question": question, "context": context, "messages": messages, "sources": sources, "sid": sid}, None

    def query(self, question: str, top_k: int = 8, session_id: str = None, doc_name: str = None) -> QueryResult:
        sid = session_id or self.session_id or "default"
        start_time = time.time()

        prepared, error = self._prepare_context(question, sid, doc_name, top_k)
        if error:
            self.tracker.save(ExecutionTrace(question=question, route="blocked", answer=error, total_ms=0))
            return QueryResult(answer=error, context=[], sources=[])

        if prepared["route"] == "cached":
            return QueryResult(answer=prepared["answer"], context=[], sources=prepared["sources"])

        if prepared["route"] == "agent":
            captured_calls = []
            with self._agent_lock:
                self._wrap_agent_tools(captured_calls)
                try:
                    answer = self.agent.run(prepared["question"])
                finally:
                    self._unwrap_agent_tools()
            context = []
            sources = []
            tool_calls = [ToolCall(**c) for c in captured_calls]
        else:
            answer = generate(prepared["messages"])
            context = prepared["context"]
            sources = prepared["sources"]
            tool_calls = []

        total_ms = (time.time() - start_time) * 1000
        self.tracker.save(ExecutionTrace(
            question=question, route=prepared["route"], answer=answer,
            total_ms=total_ms, tool_calls=tool_calls,
        ))
        output_check = check_output(answer)
        if output_check.filtered:
            answer = output_check.text
        self.memory.add_message(sid, "user", question)
        self.memory.add_message(sid, "assistant", answer)
        if self.memory.should_summarize(sid):
            self.memory.summarize_old_rounds(sid)
        self._cache.set(question, answer)
        return QueryResult(answer=answer, context=context, sources=sources)

    def _wrap_agent_tools(self, captured_calls: list):
        """Wrap each agent tool's func to capture input/output/timing."""
        self._original_funcs = {}
        for tool in self.agent.tools:
            original_func = tool.func
            self._original_funcs[tool.name] = original_func
            tool_name = tool.name

            def make_wrapper(name, func):
                def wrapper(inp):
                    t0 = time.time()
                    output = func(inp)
                    duration_ms = (time.time() - t0) * 1000
                    captured_calls.append(
                        {
                            "tool_name": name,
                            "input": str(inp),
                            "output": str(output)[:500],
                            "duration_ms": duration_ms,
                        }
                    )
                    return output

                return wrapper

            tool.func = make_wrapper(tool_name, original_func)

    def _unwrap_agent_tools(self):
        """Restore original tool functions."""
        for tool in self.agent.tools:
            if tool.name in self._original_funcs:
                tool.func = self._original_funcs[tool.name]
        self._original_funcs = {}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="RAG Pipeline CLI")
    parser.add_argument("file", help="Path to the document file (.txt, .md)")
    args = parser.parse_args()

    logger.info("Indexing %s...", args.file)
    pipeline = RAGPipeline(args.file)
    logger.info("Ready. Enter your questions (Ctrl+C to exit).")

    try:
        while True:
            question = input("Q: ")
            if not question.strip():
                continue
            answer = pipeline.query(question)
            logger.info("A: %s", answer.answer)
    except (EOFError, KeyboardInterrupt):
        logger.info("Bye.")


if __name__ == "__main__":
    main()
