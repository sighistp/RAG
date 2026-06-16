"""知识库元数据生成测试。"""
from unittest.mock import patch


def test_generate_toc_returns_dict():
    """generate_toc 应该返回目录字典。"""
    from rag.kb_metadata import generate_toc
    with patch("rag.kb_metadata.generate", return_value='{"title": "测试文档", "sections": [{"title": "第一章"}]}'):
        result = generate_toc("这是文档内容...")
    assert isinstance(result, dict)
    assert result["title"] == "测试文档"
    assert len(result["sections"]) == 1


def test_generate_toc_handles_markdown_json():
    """LLM 返回 markdown 包裹的 JSON 时应该正确提取。"""
    from rag.kb_metadata import generate_toc
    with patch("rag.kb_metadata.generate", return_value='```json\n{"title": "测试", "sections": []}\n```'):
        result = generate_toc("内容")
    assert result["title"] == "测试"


def test_generate_toc_handles_invalid_json():
    """LLM 返回非 JSON 时应该返回兜底结构。"""
    from rag.kb_metadata import generate_toc
    with patch("rag.kb_metadata.generate", return_value="这是一段文字，不是JSON"):
        result = generate_toc("内容")
    assert isinstance(result, dict)
    assert "title" in result
    assert "sections" in result


def test_generate_toc_handles_llm_error():
    """LLM 调用失败时应该返回兜底结构。"""
    from rag.kb_metadata import generate_toc
    with patch("rag.kb_metadata.generate", side_effect=Exception("API error")):
        result = generate_toc("内容")
    assert result["title"] == "未知"
    assert result["sections"] == []


def test_generate_summary_returns_string():
    """generate_summary 应该返回概述字符串。"""
    from rag.kb_metadata import generate_summary
    with patch("rag.kb_metadata.generate", return_value="本文介绍了RAG系统的架构设计。"):
        result = generate_summary("文档内容...")
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_summary_handles_error():
    """LLM 调用失败时应该返回空字符串。"""
    from rag.kb_metadata import generate_summary
    with patch("rag.kb_metadata.generate", side_effect=Exception("API error")):
        result = generate_summary("内容")
    assert result == ""
