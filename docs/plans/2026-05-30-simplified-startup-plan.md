# 简化启动 + 文件夹自动索引 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 RAG 系统精简为两服务（API + 用户端），文件通过 `data/upload/` 文件夹管理，启动时自动全量索引。

**Architecture:** 新增 `folder_indexer.py` 模块负责文件夹扫描和批量索引，重写 `start_all.py` 集成索引流程并只启动 API + 用户端两个服务。

**Tech Stack:** Python, FastAPI, Streamlit, Qdrant, 百炼 Embedding API

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `rag/folder_indexer.py` | 新建 | 文件夹扫描 + 全量索引逻辑 |
| `tests/test_folder_indexer.py` | 新建 | folder_indexer 单元测试 |
| `start_all.py` | 重写 | 集成索引，只启动 API + 用户端 |
| `data/upload/.gitkeep` | 新建 | 数据文件夹占位 |

---

### Task 1: 创建 `rag/folder_indexer.py` — scan_folder

**Files:**
- Create: `rag/folder_indexer.py`
- Test: `tests/test_folder_indexer.py`

- [ ] **Step 1: Write the failing tests for scan_folder**

```python
# tests/test_folder_indexer.py
"""Tests for folder_indexer module."""
import os
import pytest
from unittest.mock import patch


def test_scan_folder_returns_supported_files(tmp_path):
    """scan_folder should return only supported file types."""
    from rag.folder_indexer import scan_folder

    # Create test files
    (tmp_path / "doc.txt").write_text("hello")
    (tmp_path / "doc.md").write_text("# title")
    (tmp_path / "doc.pdf").touch()
    (tmp_path / "image.png").touch()  # unsupported
    (tmp_path / "data.csv").touch()   # unsupported

    result = scan_folder(str(tmp_path))

    basenames = [os.path.basename(f) for f in result]
    assert "doc.txt" in basenames
    assert "doc.md" in basenames
    assert "doc.pdf" in basenames
    assert "image.png" not in basenames
    assert "data.csv" not in basenames


def test_scan_folder_returns_empty_for_empty_dir(tmp_path):
    """scan_folder should return empty list for empty directory."""
    from rag.folder_indexer import scan_folder

    result = scan_folder(str(tmp_path))
    assert result == []


def test_scan_folder_raises_on_missing_dir():
    """scan_folder should raise FileNotFoundError for missing directory."""
    from rag.folder_indexer import scan_folder

    with pytest.raises(FileNotFoundError):
        scan_folder("/nonexistent/path")


def test_scan_folder_recursive(tmp_path):
    """scan_folder should find files in subdirectories."""
    from rag.folder_indexer import scan_folder

    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_text("content")
    (tmp_path / "root.md").write_text("# root")

    result = scan_folder(str(tmp_path))
    basenames = [os.path.basename(f) for f in result]
    assert "deep.txt" in basenames
    assert "root.md" in basenames
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_folder_indexer.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'rag.folder_indexer'"

- [ ] **Step 3: Implement scan_folder**

```python
# rag/folder_indexer.py
"""文件夹扫描 + 全量索引模块。"""
import os
import time

from rag.loader import SUPPORTED_EXTENSIONS


def scan_folder(folder_path: str) -> list[str]:
    """扫描文件夹，递归返回所有支持格式的文件绝对路径列表。

    Args:
        folder_path: 文件夹路径。

    Returns:
        支持的文件绝对路径列表。

    Raises:
        FileNotFoundError: 文件夹不存在。
    """
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_folder_indexer.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add rag/folder_indexer.py tests/test_folder_indexer.py
git commit -m "feat: add folder_indexer.scan_folder for file discovery"
```

---

### Task 2: 实现 index_folder — 全量索引逻辑

**Files:**
- Modify: `rag/folder_indexer.py`
- Test: `tests/test_folder_indexer.py`

- [ ] **Step 1: Write the failing tests for index_folder**

```python
# Append to tests/test_folder_indexer.py


@patch("rag.folder_indexer.embed")
@patch("rag.folder_indexer.add")
@patch("rag.folder_indexer.clear")
@patch("rag.folder_indexer.chunk")
@patch("rag.folder_indexer.load")
def test_index_folder_returns_stats(mock_load, mock_chunk, mock_clear, mock_add, mock_embed, tmp_path):
    """index_folder should return stats dict with files, chunks, seconds."""
    from rag.folder_indexer import index_folder
    from rag.models import Chunk

    (tmp_path / "a.txt").write_text("content a")
    (tmp_path / "b.txt").write_text("content b")

    mock_load.return_value = "some text"
    mock_chunk.return_value = [Chunk(text="chunk", doc_name="a.txt", chunk_index=0)]
    mock_embed.return_value = [[0.1] * 1024]

    result = index_folder(str(tmp_path))

    assert result["files"] == 2
    assert result["chunks"] == 2
    assert result["seconds"] > 0
    mock_clear.assert_called_once()


@patch("rag.folder_indexer.embed")
@patch("rag.folder_indexer.add")
@patch("rag.folder_indexer.clear")
@patch("rag.folder_indexer.chunk")
@patch("rag.folder_indexer.load")
def test_index_folder_skips_unsupported(mock_load, mock_chunk, mock_clear, mock_add, mock_embed, tmp_path):
    """index_folder should skip unsupported files without error."""
    from rag.folder_indexer import index_folder
    from rag.models import Chunk

    (tmp_path / "ok.txt").write_text("content")
    (tmp_path / "skip.png").touch()

    mock_load.return_value = "content"
    mock_chunk.return_value = [Chunk(text="chunk", doc_name="ok.txt", chunk_index=0)]
    mock_embed.return_value = [[0.1] * 1024]

    result = index_folder(str(tmp_path))

    assert result["files"] == 1
    mock_load.assert_called_once()


@patch("rag.folder_indexer.embed")
@patch("rag.folder_indexer.add")
@patch("rag.folder_indexer.clear")
@patch("rag.folder_indexer.chunk")
@patch("rag.folder_indexer.load")
def test_index_folder_empty_dir(mock_load, mock_chunk, mock_clear, mock_add, mock_embed, tmp_path):
    """index_folder should handle empty directory gracefully."""
    from rag.folder_indexer import index_folder

    result = index_folder(str(tmp_path))

    assert result["files"] == 0
    assert result["chunks"] == 0
    mock_clear.assert_called_once()
    mock_load.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_folder_indexer.py::test_index_folder_returns_stats -v`
Expected: FAIL with "AttributeError: module 'rag.folder_indexer' has no attribute 'index_folder'"

- [ ] **Step 3: Implement index_folder**

```python
# Add to rag/folder_indexer.py after scan_folder

from rag.loader import load, SUPPORTED_EXTENSIONS
from rag.chunker import chunk
from rag.embedder import embed
from rag.vector_store import add, clear


def index_folder(folder_path: str) -> dict:
    """全量索引文件夹内所有文件到默认向量库集合。

    流程：清空集合 → 逐文件 load+chunk → 批量 embed+add。

    Args:
        folder_path: 数据文件夹路径。

    Returns:
        统计信息 {"files": int, "chunks": int, "seconds": float}。
    """
    start = time.time()
    files = scan_folder(folder_path)

    # 清空默认集合
    clear()

    if not files:
        return {"files": 0, "chunks": 0, "seconds": round(time.time() - start, 2)}

    # 逐文件 load + chunk，收集所有 chunks
    from rag.models import Chunk
    all_chunks: list[Chunk] = []
    loaded = 0
    for fpath in files:
        try:
            text = load(fpath)
            doc_name = os.path.basename(fpath)
            file_chunks = chunk(text, doc_name=doc_name)
            all_chunks.extend(file_chunks)
            loaded += 1
        except Exception as e:
            print(f"  [警告] 跳过 {os.path.basename(fpath)}: {e}")

    if not all_chunks:
        return {"files": loaded, "chunks": 0, "seconds": round(time.time() - start, 2)}

    # 批量 embed + add
    texts = [c.text for c in all_chunks]
    embeddings = embed(texts)
    add(all_chunks, embeddings)

    elapsed = round(time.time() - start, 2)
    return {"files": loaded, "chunks": len(all_chunks), "seconds": elapsed}
```

- [ ] **Step 4: Run all folder_indexer tests**

Run: `pytest tests/test_folder_indexer.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add rag/folder_indexer.py tests/test_folder_indexer.py
git commit -m "feat: add folder_indexer.index_folder for batch indexing"
```

---

### Task 3: 创建 data/upload/ 目录

**Files:**
- Create: `data/upload/.gitkeep`

- [ ] **Step 1: Create the directory and .gitkeep**

```bash
mkdir -p data/upload
touch data/upload/.gitkeep
```

- [ ] **Step 2: Commit**

```bash
git add data/upload/.gitkeep
git commit -m "feat: add data/upload directory for file-based indexing"
```

---

### Task 4: 重写 start_all.py

**Files:**
- Modify: `start_all.py`

- [ ] **Step 1: Rewrite start_all.py**

```python
"""一键启动 RAG 系统：扫描文件夹 → 索引 → API 后端 + 用户端。"""
import argparse
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def kill_port(port: int):
    """杀掉占用指定端口的进程（Windows）。"""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit() and int(pid) > 0:
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        capture_output=True, timeout=5,
                    )
    except Exception:
        pass


def wait_for_port(port: int, timeout: int = 30):
    """等待端口就绪。"""
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def is_port_free(port: int) -> bool:
    """检查端口是否空闲。"""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return False
    except OSError:
        return True


def main():
    parser = argparse.ArgumentParser(description="RAG 系统一键启动")
    parser.add_argument(
        "--data-folder",
        default=str(PROJECT_ROOT / "data" / "upload"),
        help="数据文件夹路径（默认: data/upload/）",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  RAG 知识库系统 - 一键启动")
    print("=" * 50)
    print(f"  数据文件夹: {args.data_folder}")
    print("  API 后端:   http://localhost:8000")
    print("  用户端:     http://localhost:8502")
    print("=" * 50)
    print()

    # 0. 清理残留进程
    ports = [8000, 8502]
    need_clean = [p for p in ports if not is_port_free(p)]
    if need_clean:
        print(f"检测到端口 {need_clean} 被占用，正在清理残留进程...")
        for p in need_clean:
            kill_port(p)
        time.sleep(1)
        print("清理完成。")
        print()

    # 1. 扫描文件夹并索引
    print("[1/2] 扫描文件夹并索引...")
    from rag.folder_indexer import index_folder
    try:
        stats = index_folder(args.data_folder)
        print(f"  索引完成: {stats['files']} 个文件, {stats['chunks']} 个分块, 耗时 {stats['seconds']}s")
    except FileNotFoundError:
        print(f"  [警告] 文件夹不存在: {args.data_folder}")
        print("  跳过索引，系统将以空知识库启动。")
    print()

    # 2. 启动 API
    print("[2/2] 启动服务...")
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "rag.api:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(PROJECT_ROOT),
    )
    if wait_for_port(8000, timeout=30):
        print("  API 后端已就绪 (http://localhost:8000)")
    else:
        print("  [警告] API 启动超时，请检查终端窗口")

    # 3. 启动用户端
    user = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "rag/user_gui.py",
         "--server.port", "8502", "--server.headless", "true"],
        cwd=str(PROJECT_ROOT),
    )
    if wait_for_port(8502, timeout=30):
        print("  用户端已就绪 (http://localhost:8502)")
    else:
        print("  [警告] 用户端启动超时")

    # 打开浏览器
    time.sleep(1)
    webbrowser.open("http://localhost:8502")

    print()
    print("服务已启动！")
    print("  用户端: http://localhost:8502  (提问界面)")
    print("  API:    http://localhost:8000  (接口服务)")
    print()
    print("按 Ctrl+C 停止所有服务。")
    print()

    processes = [("API", api), ("用户端", user)]
    try:
        while True:
            time.sleep(1)
            for name, p in processes:
                if p.poll() is not None:
                    print(f"[警告] {name} 已退出 (code={p.returncode})")
                    processes.remove((name, p))
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        for _, p in processes:
            p.terminate()
        print("已停止。")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add start_all.py
git commit -m "feat: rewrite start_all.py with folder indexing and 2-service startup"
```

---

### Task 5: 更新文档

**Files:**
- Modify: `docs/superpowers/plans/dev-log.md`
- Modify: `docs/superpowers/plans/rag-system-plan.md`

- [ ] **Step 1: Update dev-log.md**

Append to dev-log:

```markdown
## 2026-05-30 简化启动 + 文件夹自动索引

### 背景
原系统启动 3 个服务（API + 管理端 + 用户端），Streamlit 启动慢，占用资源多。

### 改动
- 新增 `rag/folder_indexer.py`：文件夹扫描 + 全量索引
- 重写 `start_all.py`：启动时自动扫描 `data/upload/`，只启动 API + 用户端
- 管理端代码保留，可手动启动

### 效果
- 启动服务从 3 个减到 2 个
- 文件管理从 GUI 上传改为文件夹放置
- 启动时自动全量索引，无需手动操作
```

- [ ] **Step 2: Update rag-system-plan.md**

Add to the plan:

```markdown
### Task 39: 简化启动 + 文件夹自动索引

- [x] 新增 `rag/folder_indexer.py`（scan_folder + index_folder）
- [x] 重写 `start_all.py`（文件夹扫描 + 2 服务启动）
- [x] 创建 `data/upload/` 数据目录
- [x] 单元测试（7 个）
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/dev-log.md docs/superpowers/plans/rag-system-plan.md
git commit -m "docs: add simplified startup to dev-log and plan"
```

---

## Verification

Run the full test suite:
```bash
pytest tests/ -v
```

Run the startup script:
```bash
python start_all.py
```

Expected output:
```
==================================================
  RAG 知识库系统 - 一键启动
==================================================
  数据文件夹: C:\Users\lahm\Desktop\RAG\data\upload
  API 后端:   http://localhost:8000
  用户端:     http://localhost:8502
==================================================

[1/2] 扫描文件夹并索引...
  索引完成: X 个文件, Y 个分块, 耗时 Zs

[2/2] 启动服务...
  API 后端已就绪 (http://localhost:8000)
  用户端已就绪 (http://localhost:8502)

服务已启动！
  用户端: http://localhost:8502  (提问界面)
  API:    http://localhost:8000  (接口服务)
```
