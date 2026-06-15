"""追问建议测试。"""
from unittest.mock import patch


def test_suggest_questions_returns_list():
    """suggest_questions 应该返回问题列表。"""
    from rag.suggest import suggest_questions
    with patch("rag.suggest.generate", return_value="1. 什么是 mTLS？\n2. 如何配置？\n3. 有哪些模式？"):
        result = suggest_questions("什么是 mTLS？", "mTLS 是双向 TLS 认证...")
    assert isinstance(result, list)
    assert len(result) == 3


def test_suggest_questions_returns_empty_on_error():
    """LLM 调用失败时返回空列表。"""
    from rag.suggest import suggest_questions
    with patch("rag.suggest.generate", side_effect=Exception("API error")):
        result = suggest_questions("test", "test")
    assert result == []


def test_suggest_questions_parses_numbered_list():
    """应该解析带编号的列表。"""
    from rag.suggest import suggest_questions
    with patch("rag.suggest.generate", return_value="1. 问题一\n2. 问题二\n3. 问题三"):
        result = suggest_questions("q", "a")
    assert result == ["问题一", "问题二", "问题三"]
