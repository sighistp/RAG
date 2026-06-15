# 数据清洗管道设计

> 文档加载后、分块前的数据清洗，保证进入 RAG 管道的数据质量。

## 背景

当前 `rag/loader.py` 直接读取文件内容，没有清洗步骤。问题：

1. **编码混用** — GBK/GB2312/UTF-8 文件混用，直接读取可能乱码
2. **特殊字符** — 零宽字符、BOM、控制字符混在文本中影响分块和检索
3. **重复内容** — 同一文档重复上传或段落重复，浪费存储和干扰检索
4. **无元数据** — 标题、作者、日期等信息丢失，无法辅助检索

## 设计

新建 `rag/cleaner.py`，在 loader 和 chunker 之间插入清洗步骤：

```
文档加载(load) → 数据清洗(clean) → 分块(chunk) → 嵌入(embed)
```

### 1. 编码检测 + 修复

用 `chardet` 库自动检测编码：

```python
def detect_and_decode(raw_bytes: bytes) -> str:
    """自动检测编码并解码。"""
    detected = chardet.detect(raw_bytes)
    encoding = detected.get("encoding", "utf-8") or "utf-8"
    try:
        return raw_bytes.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return raw_bytes.decode("utf-8", errors="replace")
```

### 2. 乱码清理

去除影响分块和检索的特殊字符：

```python
def clean_text(text: str) -> str:
    """清理特殊字符。"""
    text = text.replace("﻿", "")  # BOM
    text = text.replace("​", "")  # 零宽空格
    text = text.replace(" ", " ")  # 不间断空格 → 普通空格
    # 去除控制字符（保留换行、制表符）
    text = "".join(c for c in text if c in "\n\t" or ord(c) >= 32)
    # 合并连续空行
    import re
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
```

### 3. 去重

两层去重：

| 层 | 策略 | 说明 |
|---|------|------|
| 文档级 | MD5 hash | 相同文档不重复索引 |
| 段落级 | 相似度 > 95% 去重 | 用 difflib.SequenceMatcher 快速比对 |

```python
def deduplicate_chunks(chunks: list[str], threshold: float = 0.95) -> list[str]:
    """段落级去重。"""
    unique = []
    for chunk in chunks:
        if not any(_similarity(chunk, u) > threshold for u in unique):
            unique.append(chunk)
    return unique

def _similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()
```

### 4. 元数据提取

正则提取文档元数据：

```python
def extract_metadata(text: str) -> dict:
    """提取标题、作者、日期。"""
    import re
    metadata = {}
    # 标题：Markdown # 或 "标题："
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if title_match:
        metadata["title"] = title_match.group(1).strip()
    # 作者
    author_match = re.search(r"(?:作者|Author)[：:]\s*(.+)", text)
    if author_match:
        metadata["author"] = author_match.group(1).strip()
    # 日期
    date_match = re.search(r"(?:日期|Date)[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})", text)
    if date_match:
        metadata["date"] = date_match.group(1).strip()
    return metadata
```

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `rag/cleaner.py` | 新建 | 数据清洗管道 |
| `rag/loader.py` | 修改 | 加载后调 cleaner |
| `rag/pipeline.py` | 修改 | 集成去重逻辑 |
| `tests/test_cleaner.py` | 新建 | 清洗管道测试 |

## 测试策略

| 测试 | 验证内容 |
|------|---------|
| GBK 编码自动检测 | GBK 字节流正确解码为中文 |
| BOM/零宽字符清理 | 特殊字符被移除 |
| 文档级去重 | 相同 MD5 的文档不重复处理 |
| 段落级去重 | 相似度 > 95% 的段落被去重 |
| 元数据提取 | 标题/作者/日期被正确提取 |
| 正常文档不受影响 | 清洗不破坏原有内容 |

## 面试话术

"文档进入 RAG 管道前有清洗步骤：编码检测——chardet 自动识别 GBK/UTF-8 混用；乱码清理——去除零宽字符、BOM 等特殊符号；去重——文档级 MD5 + 段落级相似度 95% 阈值；元数据提取——正则抽取标题/作者/日期辅助检索。"
