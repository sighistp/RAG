# Changelog

## 2026-06-11

### Bug Fix: 选择文件后检索未限定文档范围

**问题描述**

用户在前端选择特定文件后提问，系统仍返回其他文档的内容。例如选择 `新建文本文档.txt` 让其总结，却返回了之前上传的 `深度学习课程设计项目报告（2）.docx` 的内容。

**根本原因**

`selectFile()` 函数仅做视觉高亮（CSS class 切换），未存储选中文件名，查询请求也未携带文件过滤参数。后端检索时搜索整个 Qdrant 集合，返回语义最相关的文档（可能是其他文件）。

**修复内容**

| 文件 | 变更 |
|------|------|
| `static/index.html` | `selectFile()` 支持点击切换选中/取消状态，查询时携带 `doc_name` 参数 |
| `rag/api.py` | `QueryRequest` 新增 `doc_name: str \| None` 字段，透传至 pipeline |
| `rag/pipeline.py` | `query()` 方法接收 `doc_name` 并传递给 retriever |
| `rag/retriever.py` | `retrieve()` 支持 `doc_name` 过滤，BM25 结果按文档名筛选 |
| `rag/vector_store.py` | `search_collection()` 支持 Qdrant 向量过滤（`FieldCondition` + `MatchValue`） |

**行为变更**

- 选择文件 → 检索限定在该文档内
- 取消选择（再次点击） → 搜索全部文档
- 未选择任何文件 → 搜索全部文档（向后兼容）

**测试**

- 所有 25 个现有测试通过
- `ruff check` 无新增 error
