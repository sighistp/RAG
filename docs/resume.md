# 简历项目经历

## RAG 智能知识库系统 | 独立开发 | 2026.05 - 2026.06

**技术栈：** Python · FastAPI · Vue 3 · LangChain · Qdrant · DeepSeek · SQLite

基于 RAG 的中文知识库问答系统，支持多知识库管理、多轮对话、流式输出。

**检索优化：**
- 纯向量检索对口语化查询（如"服务挂了怎么摘除"）召回失败 → 引入 BM25 稀疏检索 + jieba 分词 + RRF 融合，再加 LLM 查询改写（口语→正式），口语化提问召回从失败变为可用
- 初筛结果噪声大（关键词干扰 chunk 排名靠前）→ 二阶段精排：初筛 top16 经 BGE Reranker 精排到 top5，相关文档排序显著提升
- 用户反馈无法反哺检索 → 设计 chunk 级反馈权重衰减机制（0.2–2.0），正向反馈提升相关 chunk 排名，形成检索持续优化闭环

**Agent 设计：**
- 设计 RAG/Agent 双模路由，LLM 根据意图自动分流；初期路由过于激进（"多少件"这类统计词误触发 Agent），通过迭代 router prompt 规则解决
- Agent 集成 4 个自研工具（检索/计算/SQL/图表），SQL 工具三重防护（只读 pragma + 关键字黑名单 + 禁止多语句），计算工具基于 AST 沙箱仅允许四则运算
- 工具调用结果自检 + 反思重试闭环：空结果自动 retry，输出经 LLM 质量自评不通过则追加 refinement 重新生成（最多 3 轮）；代码审查发现反思函数从未被调用（Critical），修复后闭环生效

**工程规范：**
- 自研韧性模块：熔断器（closed/open/half-open 三态）+ 指数退避重试 + Bloom Filter 防缓存穿透 + TTL 抖动防缓存雪崩；代码审查发现 half_open 状态放行所有请求（Critical），修复为只放一个探测请求
- 全链路可观测：每次查询记录路由、延迟、tool call、chunk hash 到 SQLite，支持知识缺口分析（追踪低置信/未命中查询）
- 304 个测试覆盖全模块，Ruff + pre-commit 强制代码规范，20+ 设计文档沉淀（spec → plan → 实现完整链路）
