"""文件夹扫描 + 全量索引模块。"""

import hashlib
import json
import logging
import os
import time

from rag.loader import SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)


def compute_file_hash(file_path: str) -> str:
    """计算文件的 MD5 hash。"""
    h = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def load_index_state(state_path: str) -> dict:
    """加载索引状态文件。"""
    if not os.path.exists(state_path):
        return {}
    with open(state_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_index_state(state_path: str, state: dict):
    """保存索引状态文件。"""
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def diff_index(current_hashes: dict, stored_state: dict) -> tuple[list, list, list]:
    """对比当前文件 hash 与存储状态，返回 (新增, 修改, 删除) 的文件名列表。

    stored_state 支持两种格式:
    - 嵌套格式: {"files": {"name": {"hash": "..."}}}
    - 平铺格式: {"name": "hash"}（兼容测试）
    """
    if "files" in stored_state:
        stored_hashes = {name: info["hash"] for name, info in stored_state["files"].items()}
    else:
        stored_hashes = dict(stored_state)
    added = [name for name in current_hashes if name not in stored_hashes]
    modified = [name for name in current_hashes if name in stored_hashes and current_hashes[name] != stored_hashes[name]]
    deleted = [name for name in stored_hashes if name not in current_hashes]
    return added, modified, deleted


def scan_folder(folder_path: str) -> list[str]:
    """扫描文件夹，递归返回所有支持格式的文件绝对路径列表。"""
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(f"文件夹不存在: {folder_path}")

    result = []
    for root, _dirs, files in os.walk(folder_path):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                result.append(os.path.join(root, f))
    result.sort()
    return result


def index_folder(folder_path: str) -> dict:
    """全量索引文件夹内所有文件到默认向量库集合。

    流程：清空集合 → 逐文件 load+chunk → 批量 embed+add。
    """
    import rag.chunker as _chunker
    import rag.embedder as _embedder
    import rag.loader as _loader
    import rag.vector_store as _vs

    start = time.time()
    files = scan_folder(folder_path)

    # 清空默认集合
    _vs.clear()

    if not files:
        return {"files": 0, "chunks": 0, "seconds": round(time.time() - start, 2)}

    # 逐文件 load + chunk，收集所有 chunks
    from rag.models import Chunk

    all_chunks: list[Chunk] = []
    loaded = 0
    for fpath in files:
        try:
            text = _loader.load(fpath)
            doc_name = os.path.basename(fpath)
            file_chunks = _chunker.chunk(text, doc_name=doc_name)
            all_chunks.extend(file_chunks)
            loaded += 1
        except Exception as e:
            logger.warning("跳过 %s: %s", os.path.basename(fpath), e)

    if not all_chunks:
        return {"files": loaded, "chunks": 0, "seconds": round(time.time() - start, 2)}

    # 批量 embed + add
    texts = [c.text for c in all_chunks]
    embeddings = _embedder.embed(texts)
    _vs.add(all_chunks, embeddings)

    elapsed = round(time.time() - start, 2)
    return {"files": loaded, "chunks": len(all_chunks), "seconds": elapsed}
