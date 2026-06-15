# 简化启动 + 文件夹自动索引 设计文档

## 目标

将 RAG 系统精简为 API 单服务，文件管理改为文件夹扫描方式，提升启动速度和使用便捷性。

## 架构

```
python start.py
  ├── 1. 扫描 data/upload/ → 全量索引到向量库
  ├── 2. 启动 API (uvicorn, port 8000)
  └── 3. 打开浏览器
```

## 索引策略

- **全量重建**：每次启动清空默认向量库集合，重新索引 `data/upload/` 下所有文件
- 支持格式：.txt / .md / .pdf / .docx / .xlsx（复用 `rag.loader.SUPPORTED_EXTENSIONS`）
- 跳过不支持的文件类型，打印警告
- 未来可升级为增量索引（记录已索引文件状态）

## 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `rag/folder_indexer.py` | 新建 | 文件夹扫描 + 批量索引模块 |
| `start_all.py` | 重写 | 集成文件夹扫描，只启动 2 个服务 |
| `data/upload/` | 新建目录 | 用户数据文件夹，含 .gitkeep |
| `tests/test_folder_indexer.py` | 新建 | folder_indexer 单元测试 |

## `rag/folder_indexer.py` 接口

```python
def scan_folder(folder_path: str) -> list[str]:
    """扫描文件夹，返回支持的文件路径列表。"""

def index_folder(folder_path: str) -> dict:
    """全量索引文件夹内所有文件。返回 {"files": N, "chunks": N, "seconds": X}。"""
```

内部流程：
1. `scan_folder()` — 遍历目录，过滤 `SUPPORTED_EXTENSIONS`
2. 清空默认集合（`vector_store.clear()`）
3. 逐文件：`loader.load()` → `chunker.chunk()` → 收集所有 chunks
4. 批量 `embedder.embed()` → `vector_store.add()`
5. 返回统计信息

## `start_all.py` 流程

1. 解析参数（`--data-folder` 默认 `data/upload/`）
2. 检查端口 8000/8502，清理残留进程
3. 调用 `folder_indexer.index_folder(data_folder)`，打印索引统计
4. 启动 uvicorn（API, port 8000）
5. 等待端口就绪
6. 启动 streamlit（用户端, port 8502）
7. 等待端口就绪
8. 打开浏览器
9. Ctrl+C 停止所有服务

## 不变的部分

- API 接口不变（`/query`, `/index`, `/health`, `/knowledge-bases/*`）
- Web UI 不变（static/index.html）
- 向量库、嵌入模型、检索逻辑均不变
