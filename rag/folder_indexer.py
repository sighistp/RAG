"""文件夹扫描 + 全量索引模块。"""

import logging
import os
import time

from rag.loader import SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)


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
