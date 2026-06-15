# 简历项目经历

## RAG 智能知识库系统 | 独立开发 | 2026.05 - 2026.06

**技术栈：** Python、FastAPI、Qdrant、DeepSeek、百炼、SQLite、原生 HTML/CSS/JS

基于 RAG 的企业级知识库问答系统，支持多用户、多轮对话、Agent 工具调用。

- **检索优化：** 向量 + BM25 + RRF 混合检索 + rerank 精排 + 查询改写，Hit Rate 82% → 91%
- **并发性能：** 异步端点 + 读写锁 + embedding 缓存，压测 QPS 1.9，0% 错误率
- **安全防护：** SQL 注入白名单、XSS 转义、JWT 认证、用户数据隔离
- **Agent 化：** LangChain ReAct + 4 工具（计算/SQL/图表/导入），路由自动分流
- **工程规范：** TDD（25+ 测试）、Ruff lint、集中日志、请求 ID 追踪
