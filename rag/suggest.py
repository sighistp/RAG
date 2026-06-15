"""追问建议生成。"""
import logging
import re

from rag.generator import generate

logger = logging.getLogger(__name__)

SUGGEST_PROMPT = """基于以下问答，生成 3 个用户可能想追问的问题。只输出问题，每行一个，用编号列表格式。

问题：{question}
回答：{answer}

追问："""


def suggest_questions(question: str, answer: str) -> list[str]:
    """生成 2-3 个追问建议。失败时返回空列表。"""
    try:
        prompt = SUGGEST_PROMPT.format(question=question, answer=answer[:500])
        messages = [{"role": "user", "content": prompt}]
        result = generate(messages)
        questions = []
        for line in result.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            cleaned = re.sub(r"^\d+[\.\)、]\s*", "", line)
            if cleaned:
                questions.append(cleaned)
        return questions[:3]
    except Exception as e:
        logger.warning("追问建议生成失败: %s", e)
        return []
