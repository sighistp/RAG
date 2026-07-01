# 李永红

**联系方式：** 18215878978 · 19196127269@163.com
**求职岗位：** AI应用开发

---

## 教育背景

**2023.9 – 2027.7** · 北京科技大学天津学院 · 人工智能专业

课程：自然语言处理、计算机视觉、深度学习与神经网络、脑与认知科学、Python、数据结构

---

## 个人能力及特长

**深入掌握：** RAG 架构设计（混合检索+RRF 融合+反馈权重优化，Hit Rate 100%）、AI Agent 设计（路由分流+工具反射+答案自检）、Prompt Engineering（版本化管理+模板变量）、Python

**熟练掌握：** LangChain/LangGraph（ReAct Agent + StateGraph 状态机编排）、FastAPI（REST + WebSocket + JWT 认证）、Vue 3 + TypeScript（Pinia + WebSocket 实时通信）、SQLite（多库分离+并发控制）、Qdrant 向量数据库、Redis（缓存+Bloom Filter 防穿透+自动降级）、pytest（577+ 项测试，TDD 流程）

**熟悉：** Docker/Docker Compose（多服务编排）、GitHub Actions CI/CD、BM25 稀疏检索+RRF 融合、多格式文档解析（PDF/DOCX/XLSX/CSV）

**AI 工具：** Claude、Codex（日常开发重度使用）

---

## 项目经历

### RAG 智能知识库系统 | 独立开发

**项目仓库：** github.com/sighistp/RAG · **线上演示：** 39.105.89.99:8000
**技术栈：** Python · FastAPI · LangChain · Qdrant · DeepSeek · Vue 3 · Redis · Docker

**业务场景：** 面向企业知识管理，支持多用户、多知识库、三级文档权限管控（private/shared/public + owner/admin 绕过 + 共享机制），部署线上可实际使用。

**Agent 设计（自研）：** 基于 LangChain 的 LLM 路由层动态分流 RAG/Agent 路径；双重反射（工具失败重试 + 答案自评追问）；调用全链路追踪

**检索优化：** Dense + Sparse + RRF 融合（含反馈权重）+ BGE-reranker 重排；55 题跨 9 学科 Hit Rate 100%；用户反馈权重驱动检索质量持续优化

**稳定性与安全：** 熔断降级（三条链路独立）；缓存防护（Bloom Filter + TTL 抖动）；注入检测 + SQL 白名单 + AST 安全求值 + 输出过滤

**工程架构：** 分层架构（API→Pipeline→Guard/Cache/Router/Retriever/Agent）+ Redis 缓存（自动降级到内存）+ Docker Compose 部署 + YAML 版本化 Prompt 管理 + 577 项测试；50 并发压测 QPS 8.1，P50 330ms，P95 6.3s

---

### DevTeam — 多 Agent 协同代码生成平台 | 独立开发

**项目仓库：** github.com/sighistp/agents.git
**技术栈：** Python · FastAPI · LangGraph · Vue 3 · WebSocket · SQLite · Docker

**业务场景：** 输入一句话需求，6 个 Agent 自动完成需求分析→架构设计→代码开发→测试→审查→交付，支持实时可视化与人工干预。

**多 Agent 编排（自研状态机）：** LangGraph StateGraph 有向图，条件路由 + 测试/审查修复循环 + 架构回退；Human-in-the-loop 暂停等待人工确认；Proposer-Critic 对抗辩论实验后改为工具执行验证，LLM 调用减少质量提升

**工具执行与沙箱安全：** 工具调用循环（≤8 步）+ 角色最小权限；路径穿越防护 + 危险模式扫描；沙箱隔离（环境变量剥离 + 内存限制 + 进程树杀死）

**WebSocket 实时通信：** Graph 后台线程执行，asyncio.Queue 桥接推送；Epoch 计数器防止新旧任务消息竞态

**工程规范：** 双层质量保障（Prompt 正负例 + Pydantic 强校验）；240 项测试覆盖；Docker 容器化部署

---

## 个人评价

- AI 原生开发者，日常使用 Claude / Codex 辅助架构设计与代码实现，能快速将想法落地为可运行的系统
- 习惯用数据驱动优化：评估指标、压测数据、反馈闭环，不接受"跑通就行"
- 独立从零构建并部署两个完整 AI 系统，能将业务需求拆解为技术方案并落地
