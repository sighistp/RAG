"""查询改写模块 — 将口语化问题改写为正式问法，提升检索命中率"""

from rag.prompt_manager import PromptManager
from rag.resilience import retry

_pm = PromptManager()


@retry(max_attempts=2, backoff_base=0.5, retryable_exceptions=(TimeoutError, ConnectionError, OSError))
def rewrite_query(question: str) -> str:
    """将口语化问题改写为正式问法，失败时返回原问题"""
    from rag.generator import generate

    try:
        prompt = _pm.render("rewrite", question=question)
        messages = [
            {"role": "system", "content": "你是一个查询改写助手。"},
            {"role": "user", "content": prompt},
        ]
        result = generate(messages).strip()
        return result if result else question
    except Exception:
        return question
