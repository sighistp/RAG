# 简历项目经历

## RAG 智能知识库系统 | 独立开发 | 2026.05 - 2026.06

**技术栈：** Python · FastAPI · Vue 3 · LangChain · Qdrant · DeepSeek · SQLite

基于 RAG 的中文知识库问答系统，支持多知识库管理、多轮对话、流式输出。

**检索优化：**
- 纯向量检索口语化查询命中率低 → 引入 BM25 稀疏检索 + jieba 分词，RRF 融合排序，口语化提问召回明显改善
- 初筛结果噪声多 → 加 BGE Reranker 二阶段精排，相关文档排序显著提升
- 用户反馈无法反哺检索 → 设计 chunk 级反馈权重衰减机制，正向反馈提升相关 chunk 排名，逐步优化检索质量

**Agent 设计：**
- 设计 RAG/Agent 双模路由，LLM 根据意图自动分流：简单检索走 RAG，需工具调用走 Agent
- Agent 集成 4 个自研工具（检索/计算/SQL/图表），SQL 工具三重防护（只读 pragma + 关键字黑名单 + 禁止多语句），计算工具基于 AST 沙箱
- 工具调用结果自检 + 反思重试闭环：空结果自动 retry，输出经 LLM 质量自评，不通过则追加 refinement 重新生成（最多 3 轮）

**工程规范：**
- 自研韧性模块：熔断器（closed/open/half-open 三态）+ 指数退避重试 + Bloom Filter 缓存穿透防护 + TTL 缓存雪崩防护
- 全链路可观测：每次查询记录路由、延迟、tool call、chunk hash 到 SQLite，支持知识缺口分析
- 47 个测试文件覆盖全模块，Ruff + pre-commit 强制代码规范，20+ 设计文档沉淀
