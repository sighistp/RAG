"""安全层 — Prompt Injection 防护、输入净化、输出审查。"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    "忽略之前的指令",
    "忽略以上指令",
    "ignore previous",
    "ignore above",
    "system prompt",
    "系统提示",
    "你的指令是什么",
    "what are your instructions",
    "假装你是",
    "pretend you are",
    "你现在是",
    "you are now",
    "roleplay",
    "jailbreak",
    "DAN",
]

MAX_INPUT_LENGTH = 5000


@dataclass
class GuardResult:
    blocked: bool
    reason: str = ""


@dataclass
class OutputResult:
    filtered: bool
    text: str


def check_injection(text: str) -> GuardResult:
    """检测 Prompt Injection 攻击。"""
    if len(text) > MAX_INPUT_LENGTH:
        return GuardResult(blocked=True, reason=f"输入过长（最多 {MAX_INPUT_LENGTH} 字符）")
    lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern.lower() in lower:
            logger.warning("注入检测命中: pattern=%s, text_preview=%s", pattern, text[:50])
            return GuardResult(blocked=True, reason="输入包含不允许的内容")
    return GuardResult(blocked=False)


def sanitize_input(text: str) -> str:
    """净化输入：截断 + 去除控制字符。"""
    text = text[:5000]
    return "".join(c for c in text if c == "\n" or (ord(c) >= 32))


OUTPUT_LEAK_PATTERNS = ["system prompt", "系统提示", "内部路径", "api key", "sk-"]


def check_output(text: str) -> OutputResult:
    """检查 LLM 输出是否泄露敏感信息。"""
    lower = text.lower()
    for pattern in OUTPUT_LEAK_PATTERNS:
        if pattern in lower:
            filtered = re.sub(re.escape(pattern), "[已过滤]", text, flags=re.IGNORECASE)
            return OutputResult(filtered=True, text=filtered)
    return OutputResult(filtered=False, text=text)
