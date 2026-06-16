"""知识库元数据生成 — 目录提取 + 概述生成。"""
import json
import logging
import re

from rag.generator import generate

logger = logging.getLogger(__name__)


def generate_toc(content: str) -> dict:
    """LLM 提取文档标题层级结构。失败时返回兜底结构。"""
    prompt = f"""请从以下文档中提取标题层级结构，输出 JSON 格式：
{{"title": "文档标题", "sections": [{{"title": "章节标题", "subsections": [...]}}, ...]}}

文档内容：
{content[:3000]}"""
    try:
        result = generate([{"role": "user", "content": prompt}])
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"title": "未知", "sections": []}
    except Exception as e:
        logger.warning("目录生成失败: %s", e)
        return {"title": "未知", "sections": []}


def generate_summary(content: str) -> str:
    """LLM 生成文档概述。失败时返回空字符串。"""
    prompt = f"""请用 100-200 字概括以下文档的核心内容，包括：主题、覆盖范围、关键知识点。

文档内容：
{content[:2000]}"""
    try:
        return generate([{"role": "user", "content": prompt}])
    except Exception as e:
        logger.warning("概述生成失败: %s", e)
        return ""
