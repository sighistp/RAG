# 开发日志 & 问题解决记录

> 记录 RAG 系统开发过程中遇到的所有问题、根因分析和解决方案。

---

## Java 安装与环境配置（2026-05-20）

| 问题 | 原因 | 解决 |
|------|------|------|
| Winget 下载 Java 后卡在 UAC 弹窗 | 终端无法处理 GUI 权限弹窗，MSI 已缓存但未安装 | 找到缓存 MSI 路径 → `start "" "path\to.msi"` 启动 GUI 安装器让用户手动确认 |
| `java --version` 未找到 | MSI 未自动添加到 PATH | 手动设置 `JAVA_HOME` 和 `PATH` 到 `~/.bashrc` |
| `load_pdf()` 运行时报 WinError 2 | Streamlit / CLI 环境不加载 `~/.bashrc`，Java 不在 PATH | 新增 `_ensure_java_on_path()` 函数自动搜索常见安装路径（JAVA_HOME、Corretto 默认路径）并动态加入 PATH |

## PDF/DOCX 解析（2026-05-20 ~ 2026-05-23）

| 问题 | 原因 | 解决 |
|------|------|------|
| 代码审查：模块级 `import opendataloader_pdf` 导致测试无法 mock | 模块级 import 在类/函数外部，patch 找不到目标 | 改为延迟加载（`import opendataloader_pdf` 移到函数内部），mock 目标从 `rag.loader.opendataloader_pdf.convert` 改为 `opendataloader_pdf.convert` |
| 代码审查：PDF 输出文件不存在时静默返回空字符串 | 缺少日志/警告 | 添加 `warnings.warn()` |
| 代码审查：测试断言过于宽松 | `kwargs.get("format")` 可能为 None 时测试仍通过 | 改为直接断言 `kwargs.get("format") == "markdown"` |
| DOCX 表格内容被遗漏 | 原实现只用 `doc.paragraphs`，不读取表格单元格 | 改为遍历 `doc.element.body` 子元素，按文档顺序提取段落 + 表格行（`|` 分隔） |
| 中文解析失败 (pytest 显示乱码) | 文件编码问题 | 所有文件使用 utf-8 编码保存 |

## GUI 改进（2026-05-23）

| 问题 | 原因 | 解决 |
|------|------|------|
| 上传 PDF/DOCX 被拒绝 | `file_uploader(type=[...])` 只配了 `txt, md` | 加上 `pdf, docx` |
| 上传新文件后旧索引内容仍在 | 索引异常时 pipeline 未更新，旧 pipeline 残留 | `except` 块中主动清空 `st.session_state.pipeline = None` |
| 没有历史文件列表 | 缺少文件管理 UI | 侧边栏新增"已索引文件"区域，支持文件名展示 + 删除按钮（`✕`） |

## 多轮对话记忆（2026-05-23）

| 问题 | 原因 | 解决 |
|------|------|------|
| `save_summary()` 不生效 | 使用 `UPDATE` 但 sessions 表无对应行 | 改为 `INSERT ... ON CONFLICT DO UPDATE`（UPSERT） |
| `config.py qdrant_path` 指向桌面 | `Path(__file__).resolve().parent.parent` 过多一层（config.py 在项目根目录，只需 `.parent`） | 修正为 `.parent / "qdrant_data"` |
| Qdrant 锁冲突导致 e2e 测试失败 | 旧 qdrant_data 目录在桌面且被占用，新路径指向项目内 | 修正路径后删除旧目录，测试恢复正常 |
| `memory.db` 被提交到 Git | `.gitignore` 未包含 SQLite 文件 | 添加 `*.db` 规则 + `git rm --cached` 移除跟踪 |

## 测试相关

| 问题 | 原因 | 解决 |
|------|------|------|
| 测试没跑 RED 就直接写实现 | 忘记运行 pytest 验证测试失败 | 纠正流程：每次先跑测试确认 RED 再写代码 |
| Generator 测试断言 `generate("question", ["chunk1"])` 未适配新接口 | 接口从 `(query, context)` 改为 `(messages: list[dict])` | 更新测试：验证 messages 列表中包含 question 和 context 内容 |
| Pipeline 测试未 mock `clear()` | Qdrant 锁冲突导致单元测试失败 | 在 pipeline 单元测试中添加 `@patch("rag.pipeline.clear")` |
| e2e 测试 Qdrant 锁冲突——锁文件残留导致后续测试无法创建客户端 | Qdrant 本地模式使用 `portalocker` 文件锁，进程退出后 `.lock` 文件未释放 | `conftest.py` 中先 `client.close()` 再重置 `_client`；e2e 测试 mock 向量存储操作（add/clear/Retriever），避免依赖真实 Qdrant 实例 |

## 嵌入批处理限制（2026-05-23）

| 问题 | 原因 | 解决 |
|------|------|------|
| 索引文件时返回 400 "批次大小不应大于10" | 百炼 text-embedding-v4 API 限制单次请求最多 10 条文本，原实现一次性传入全部分块 | 在 `embed()` 中新增 `BATCH_SIZE = 10` 循环分批调用，每批独立请求后合并结果 |

## 代码审查修复（2026-05-23）

| 问题 | 原因 | 解决 |
|------|------|------|
| Critical: `summarize_old_rounds()` 每次调用都重新摘要已摘要过的轮次 | 缺少记录已摘要轮次数量的机制 | 新增 `sessions.last_summarized_count` 列 + `should_summarize()` 判断 `total > last_summarized_count` |
| Important: `build_messages()` 使用 user/assistant 角色存放摘要 | 摘要应属于系统提示而非对话历史 | 改为 system 角色：`{"role": "system", "content": f"对话历史摘要：{summary}"}` |
| Important: `save_summary()` 用 UPDATE 但 sessions 行可能不存在 | 无对应行时 UPDATE 不报错也不生效 | 改为 `INSERT ... ON CONFLICT DO UPDATE`（UPSERT） |
| Important: `memory.db` 被提交到 Git | `.gitignore` 未包含数据库文件 | 添加 `*.db` 到 `.gitignore` + `git rm --cached memory.db` |
| Minor: 代码审查时发现部分测试断言偏宽松 | 测试对 kwargs 取值未做严格校验 | 强化断言，直接验证具体值 |

## 检索质量优化（2026-05-23）

| 问题 | 原因 | 解决 |
|------|------|------|
| 用户问"联系开发者"时，附录 B（售后热线 400-882-3828）未被召回，回答遗漏关键信息 | top_k=5 时安全漏洞章节语义匹配更高，附录排在 top 5 之外 | `pipeline.query()` 默认 `top_k` 从 5 改为 8，提高长文档尾部内容命中概率 |

## Re-ranking 重排序（2026-05-23）

| 决策 | 说明 |
|------|------|
| 选型 | 百炼 gte-rerank API（非本地模型），与现有嵌入服务一致 |
| 数据流 | 检索 Top 16 → Reranker 精排 Top 5 → LLM 生成 |
| 新增 | `rag/reranker.py`，惰性初始化 requests.Session |
| 配置 | `bailian_rerank_model`、`rerank_top_k` |
| 预期 | Recall@5 提升 10-15%，幻觉减少 |
| 实现 | `rag/reranker.py` — 惰性初始化 requests.Session，`pipeline.query()` 三步走（retrieve → rerank → generate） |
| 测试 | 单元 3 个 + pipeline 集成 1 个，48 个回归全过 |

### Re-ranking 代码审查修复（2026-05-23）

| 问题 | 级别 | 原因 | 解决 |
|------|------|------|------|
| `pipeline.query()` 中 `rerank()` 硬编码 `top_k=5` | Critical | 绕过了 `settings.rerank_top_k` 配置 | 改为 `top_k=None`，让 Reranker 使用配置默认值 |
| `config.py` 未在 Task 1 中提交 | Important | 用户中断了 commit 流程 | 在代码审查修复中一并提交 |
| `test_rerank_returns_top_k` patch 目标错误 | Important | `patch("requests.post")` 不影响 `requests.Session().post()` | 改为 `patch.object(Reranker, "_get_client")` 返回 mock client |
| `test_rerank_returns_top_k` 返回顺序错误 | Important | 缺少 `[:top_k]` 切片 | 在 reranker.py 返回值中添加 `[:top_k]` |
| e2e 测试缺少 Reranker mock | Important | `test_e2e_full_pipeline` 未 mock Reranker 类 | 添加 `@patch("rag.pipeline.Reranker")` + 断言 `rerank.assert_called_once()` |
| pipeline 集成测试未验证 rerank 调用参数 | Minor | `test_pipeline_reranks_context` 未断言 rerank 入参 | 添加 `rerank.assert_called_once_with("question", ["chunk1", "chunk2", "chunk3"])` |

### Re-ranking 手动验证（2026-05-23）

**测试文档设计：** 8 章售后服务手册，每章 >500 字，故意制造向量检索排错场景
- 问"如何申请退款"，正确答案在第四章（退换货政策），但用词是"退换"不是"退款"
- 干扰：第二章安装指南顺带提了一句"退款"，向量检索将其排到 #2

**结果（23 个分块）：**

| 排名 | 仅向量检索 | Re-ranking 后 | 变化 |
|------|-----------|-------------|------|
| 1 | 保修注册 | 退换货申请流程 | ↑ 2 位 |
| 2 | 安装指南（提到退款） | 退换货政策概述 | ↑ 2 位 |
| 3 | 退换货申请流程 | 安装指南（提到退款） | ↓ 1 位 |
| 4 | 退换货政策概述 | 退换货章节标题 | ↑ 1 位 |

**结论：** Re-rank 成功将"直接回答退款政策"的 chunk 排到前两位，把"安装指南顺带提到退款"的干扰 chunk 压到第三。语义匹配 > 关键词匹配。

**附加脚本：**
- `scripts/compare_rerank.py` — 对比任意文档的 rerank 前后排序
- `scripts/test_rerank_effect.py` — 专用测试文档，验证 rerank 效果

## AiPy Pro 智能体开发（2026-05-23）— 已暂停

**目标：** 将 RAG 系统包装为 AiPy Pro MCP 智能体扩展，申请实习免面试录用

**技术选型：**
- MCP Server: Python `mcp` SDK + Starlette + Uvicorn (Streamable HTTP)
- 随机端口: `port=0` + monkey-patch startup 打印 `{"type": "http_start", "port": N}`
- 系统提示: `addition-system-instruction` prompt 注入
- 打包: DXT (`npx @anthropic-ai/dxt pack`)

**工具设计：**
| 工具 | 功能 | 复用模块 |
|------|------|---------|
| `index_document` | 索引文档构建知识库 | `RAGPipeline(file_path)` |
| `query_knowledge_base` | 语义检索问答 | `pipeline.query(question)` |
| `list_indexed_documents` | 查看已索引文档 | 模块级变量 |

**文件结构：**
```
aipy-agent/
├── main.py           # MCP Server
├── manifest.json     # DXT 元数据
├── pyproject.toml    # 依赖
├── icon.svg          # 图标
├── .dxtignore        # 打包排除
└── tests/            # 测试
```

**实现状态：** 🔄 进行中

### AiPy Pro 开发暂停与方向调整（2026-05-23）

**决策：** 暂搁 MCP 打包，先做核心产品

**原因：**
- MCP 协议本身在快速迭代，包装层价值有限
- 核心 RAG 系统需要真实场景验证才能证明落地能力
- 面试官更看重"能用的产品"而非"能打包的 demo"

**已删除：** `aipy-agent/` 目录（main.py、manifest.json、pyproject.toml、icon.svg、.dxtignore、tests/）

**当前计划：**
1. **Task 14（🔄 进行中）：** 落地 RAG 产品 — 用专业文档做能直接用的知识库助手
2. **Task 15（⏳ 待开始）：** 包装为 AiPy Pro 智能体 — RAG 稳定后加薄层 MCP Server + DXT 打包

**技术可行性：** MCP 层只是薄层接口转换，核心逻辑全在 `rag/pipeline.py`，随时可加

### 落地 RAG 产品测试（2026-05-23）

**测试文档：** `docs/demo-文档.md` — CloudNova 微服务平台运维手册 v3.2
- 8 个章节 + 2 个附录，涵盖架构、服务注册、流量治理、部署、监控、安全、故障排查、API
- 专业术语密集：Raft、mTLS、xDS、熔断、限流、ResourceQuota 等

**测试结果：**

| # | 问题 | 期望关键词 | 结果 |
|---|------|-----------|------|
| 1 | NovaRegistry 使用什么一致性协议？ | Raft | ✅ |
| 2 | 灰度发布分几个阶段？ | 4 | ✅ |
| 3 | mTLS 的三种配置模式是什么？ | STRICT | ✅ |
| 4 | 熔断后多久进入 HALF-OPEN 状态？ | 30 | ✅ |
| 5 | 日志保留策略中 ERROR 日志保留多久？ | 30 | ✅ |
| 6 | 服务间调用超时怎么排查？ | 熔断 | ✅ |
| 7 | 如何保证配置下发的安全性？ | mTLS | ❌ |
| 8 | 错误码 2001 是什么意思？ | 路由规则冲突 | ✅ |
| 9 | 限流规则的分布式模式基于什么实现？ | Redis | ✅ |
| 10 | 服务挂了怎么自动摘除？ | 健康检查 | ❌ |
| 11 | 怎么防止某个服务把集群资源吃光？ | ResourceQuota | ✅ |

**通过率：** 9/11（82%）

**失败分析：**
- Q7：文档未显式关联"配置下发"与"mTLS"，属于跨章节推理，检索不到合理
- Q10：问题用词太口语化（"服务挂了"），文档用"健康检查失败"。改为正式问法后通过

**结论：** RAG 系统在专业文档场景下表现良好，reranking 正常工作。口语化问题是 LLM prompt 层面可优化的方向

**辅助脚本：**
- `scripts/test_demo.py` — 11 个问题的自动化测试
- `scripts/compare_rerank.py` — rerank 前后对比

## 查询改写（2026-05-23）

**问题：** Task 14 测试中 2 个失败项均为口语化表达导致检索不到正确 chunk
- "服务挂了怎么自动摘除？" → 文档用"健康检查失败"，语义匹配失败
- 用正式问法重试后通过

**方案选型：**

| 方案 | 原理 | 通用性 | 复杂度 | 选择 |
|------|------|--------|--------|------|
| 查询改写 | LLM 把口语转正式问法 | ✅ 跨领域通用 | 低 | ✅ 采用 |
| HyDE | 生成假答案再检索 | ✅ 通用 | 中 | 后续考虑 |
| 同义词词典 | 维护术语映射表 | ❌ 需按领域定制 | 高 | 后续扩展 |

**设计：**
- 新增 `rag/query_rewriter.py`，`rewrite_query(question)` 函数
- 惰性初始化 OpenAI 客户端（与 generator 一致）
- Pipeline 集成：检索前调用改写，用改写后的问题做向量检索
- 通用 Prompt：让 LLM 将口语化表达转为更精确的书面语，保留技术术语不变

**数据流变更：**
```
原: 用户问题 → 向量检索 → rerank → 生成
新: 用户问题 → LLM改写 → 向量检索 → rerank → 生成
```

**TDD 步骤：**
1. 写 3 个失败测试（改写效果、保留术语、惰性初始化）
2. 实现 `query_rewriter.py`
3. 集成到 `pipeline.query()`
4. 全量测试回归

**测试结果：** 51 个测试全过（原 48 + 新 3）

**效果验证：**

| 口语化问题 | 改写后 | 结果 |
|-----------|--------|------|
| 服务挂了怎么自动摘除？ | 如何实现服务实例故障时的自动摘除？ | ✅ |
| 报错了咋办？ | 当出现报错时，应如何处理？ | ✅ |
| 怎么防资源被吃光？ | 如何防止系统资源被耗尽？ | ✅ |
| 这玩意儿怎么配？ | 如何配置该系统？ | ✅ |
| 数据库连不上 | 数据库连接失败，应如何处理？ | ✅ |
| 权限怎么设？ | 如何配置访问权限？ | ✅ |

**结论：** 查询改写功能有效解决了口语化问题的检索失败问题，6/6 全过。通用性强，不依赖特定文档。

## System Prompt 优化（2026-05-23）

| 问题 | 原因 | 解决 |
|------|------|------|
| LLM 可能自发翻译公司名称 | System Prompt 未约束保留原始术语 | 新增规则："保留原文中的专有名词、公司名称、技术术语不翻译，保持原始语言" |

**修改文件：** `rag/memory.py` — `SYSTEM_PROMPT` 新增一条约束

**测试结果：**
- "最活跃的开源团队都有哪些" → vLLM、LangChain AI、Ollama、Qdrant、Zilliz、Hugging Face、Significant Gravitas（全部保留英文）
- "头部科技公司谁营收最多" → Aetherix（未翻译为中文）
- 51 个测试全过

## AiPy Pro 打包与部署（2026-05-23 ~ 2026-05-24）

**打包结果：** `aipy-agent/aipy-agent.dxt`（16.7kB, 18个文件）

**代码审查修复：**

| 问题 | 级别 | 修复 |
|------|------|------|
| rewrite_query 无错误处理 | Important | 加 try/except，失败返回原问题 |
| rewrite_query 无超时 | Important | 加 timeout=30 |
| debug=True 生产环境 | Important | 改为 debug=False |
| CORS 允许所有来源 | Important | 限制为 localhost |
| 无 rewrite 失败测试 | Important | 新增 test_rewrite_query_returns_original_on_failure |
| 多文档索引覆盖 | Critical | 合并所有文档重建向量库 |
| 代码重复（aipy-agent 含 rag/ 副本） | Critical | DXT 打包需要自包含，暂手动同步 |

**部署：** 扩展已安装到 `C:\Users\lahm\AppData\Roaming\aipy-pro\extensions\@aipy-pro\rag-knowledge-base\`

**部署文档：** `docs/aipy-pro-deploy.md`

### MCP Server 验证（2026-05-24）

**验证结果：**

| 验证项 | 结果 |
|--------|------|
| `uv run main.py` 启动 | ✅ 正常启动，端口随机分配 |
| STDOUT JSON 输出 | ✅ `{"type": "http_start", "port": N}` |
| `list_tools` 返回 3 个工具 | ✅ index_document、query_knowledge_base、list_indexed_documents |
| `list_prompts` 返回 1 个 Prompt | ✅ addition-system-instruction |
| DXT 打包 | ✅ 16.7kB, 18 文件 |
| manifest.json 规范 | ✅ conversation-tool + 随机端口 + STDOUT 输出 |

**AiPy Pro 平台集成调查（面试可聊）：**

**排查过程：**

| 步骤 | 操作 | 结果 |
|------|------|------|
| 1 | 复制扩展文件到 `extensions/@aipy-pro/rag-knowledge-base/` | 文件到位，venv 创建，63 个依赖安装 |
| 2 | 重启 AiPy Pro，发送"帮我索引..." | AiPy Pro 用自己的角色扮演回复，未调用 MCP 工具 |
| 3 | 检查 SQLite `extension` 表 | 0 行记录，扩展未被注册 |
| 4 | 手动 INSERT 到 `extension` 表，重启 | 仍然不调用 MCP 工具 |
| 5 | 检查 `meta` 表 `extensions` 字段 | 发现远程集市目录 JSON（102 个扩展），我们的扩展不在其中 |
| 6 | 手动将扩展加入 `extensions` meta 列表 | 重启后列表被远程目录覆盖，我们的条目被清除 |

**根因分析：**

AiPy Pro 的扩展发现机制基于 `meta` 表的 `extensions` 字段，这是一个**远程集市目录**（类似 npm registry），每次启动时从服务器同步覆盖。本地手动复制文件 + 手动注册数据库均无法持久生效。

**推测的正确安装方式：**
1. 通过 AiPy Pro 集市 UI 一键安装（`dxt_url` 指向远程 DXT 包）
2. 或通过 `npx @anthropic-ai/dxt pack` 打包后，由平台特定流程注册
3. 平台可能还有未公开的本地扩展加载机制

**关键发现：**
- `extension` 表 — 已安装扩展的持久化存储（但平台启动时可能从 meta 字段重建）
- `extensions` meta 字段 — 远程集市目录缓存，启动时从服务器覆盖
- `task` 表 `tools` 字段 — 每个任务关联的 MCP 工具列表（如 `Trustoken-search`）
- 平台内置工具（如 `Trustoken-search`）不依赖扩展目录，是硬编码的

**结论：** 扩展本身完整符合 DXT 规范，MCP Server 独立验证通过。AiPy Pro 的扩展发现机制是平台内部实现，当前版本可能仅支持集市分发模式，不支持纯本地手动安装。

**关键文件：**
- `aipy-agent/main.py` — MCP Server 入口（3 工具 + 1 Prompt + 随机端口）
- `aipy-agent/manifest.json` — DXT 元数据
- `aipy-agent/pyproject.toml` — Python 依赖
- `aipy-agent/icon.svg` — 扩展图标

## Agent 化改造（2026-05-24）✅

**目标：** 将 RAG 系统从被动问答升级为具备 ReAct 推理能力的 Agent

**设计文档：** `docs/superpowers/specs/2026-05-24-agent-design.md`
**实现计划：** `docs/superpowers/plans/2026-05-24-agent-plan.md`

**实现过程（TDD，10 个 Task）：**

| Task | 内容 | 提交 |
|------|------|------|
| 1 | config.py 新增 agent_max_iterations、analysis_db_path | inline |
| 2 | calculate 工具 — AST 白名单安全计算 | `3eb6252` |
| 3 | sql_query 工具 — 只读 SQL 查询 | `e95ce18` |
| 4 | plot_chart 工具 — matplotlib 图表生成 | `7ccf98d` |
| 5 | import_data 工具 — Excel/CSV → SQLite | `ea60713` |
| 6 | Agent 模块 — LangChain create_agent + Router | `0b0455e` |
| 7 | Pipeline 集成 — Router 分流 + Agent 调用 | `7e2c338` |
| 8 | MCP upload_data 工具 | `95f6828` |
| 9 | GUI 数据上传（Excel/CSV） | `65dbddd` |
| 10 | 全量回归测试 + e2e 修复 | `34e9221` |

**新增文件：**
- `rag/tools.py` — 四个工具（calculate / sql_query / plot_chart / import_data）
- `rag/agent.py` — LangChain Agent + Router + ReAct 循环
- `tests/test_tools.py` — 13 个工具测试
- `tests/test_agent.py` — 4 个 Agent 测试

**修改文件：**
- `config.py` — 新增 agent 配置项
- `rag/pipeline.py` — query() 增加 router 分流
- `rag/gui.py` — sidebar 新增 Excel/CSV 上传
- `aipy-agent/main.py` — 新增 upload_data MCP 工具
- `requirements.txt` — 新增 langchain、matplotlib、openpyxl
- `tests/test_pipeline.py` — 适配 router mock，新增 2 个路由测试
- `tests/test_e2e.py` — 适配 route_question mock

**测试结果：** 71 个测试全过（原 52 + 新 19）

**技术要点：**
- LangChain 1.3.1 使用 `langchain.agents.create_agent`（现代 API，返回 langgraph state graph）
- Router: LLM 快速分类，返回 "rag" 或 "agent"
- Agent: `recursion_limit = max_iterations * 2` 防死循环
- calculate 使用 AST 白名单（+ - * / ** %），拒绝函数调用和 __import__
- sql_query 只允许 SELECT，禁止 DROP/DELETE/UPDATE/INSERT
- plot_chart 限制图表类型：bar / line / pie / scatter

**遇到的问题：**
| 问题 | 原因 | 解决 |
|------|------|------|
| calculate 浮点精度 | `(1200-1068)/1068*100` = 12.359... 不含 "12.36" | 浮点结果 round 到 2 位 |
| CSV 测试断言失败 | CSV 读取返回字符串而非数字 | 断言改为 `== "100"` |
| LangChain API 变更 | `create_react_agent`/`AgentExecutor` 在 1.3.1 中移除 | 改用 `langchain.agents.create_agent` |
| e2e 测试 assert_called_once 失败 | 新增 router 调用，LLM 被调用 2 次 | mock route_question 返回 "rag" |

### Agent 化代码审查（2026-05-24）

**审查范围：** `df6b5da..251ccc7`（10 个 commit，Agent 化全部工作）

**Strengths：**
- AST 白名单安全计算实现干净
- 工厂模式分离工具实现与 Agent 装配
- 计划忠实执行，71 测试全过
- matplotlib 使用 Agg 后端避免服务器环境问题

**已修复问题：**

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | Critical | MCP server `index_document` 手动构造 pipeline 缺少 `agent` 属性，router 分到 "agent" 时 AttributeError | 补上 `RAGAgent(retriever=_pipeline.retriever)` 初始化 |
| 2 | Important | `_parse_and_plot` 非数值输入抛原始 ValueError，Agent 难以解析 | try/except 返回友好错误信息 |
| 6 | Important | `.xls` 扩展名被接受但 openpyxl 不支持 | 移除 `.xls`，只保留 `.xlsx` |

**留作后续的问题：**

| # | 级别 | 问题 | 建议 |
|---|------|------|------|
| 3 | Important | SQL 工具 UNION 注入可泄露 schema | 解析 SQL 拒绝 UNION，或标注仅限可信输入 |
| 4 | Important | Router 每次查询都调 LLM，简单问题延迟翻倍 | 关键词预检 + LLM 兜底的两级方案 |
| 5 | Important | 图表 PNG 文件无限累积 | 添加清理机制（过期删除或 agent 结束后清理） |
| 7 | Important | `_parse_and_plot` 无测试 | 补充边界测试 |
| 8 | Important | MCP server 零测试覆盖 | 补充基本工具分发测试 |
| 9 | Minor | import_data 全列存 TEXT，排序按字典序 | 尝试类型推断 |
| 10 | Minor | test_agent_max_iterations 只检查属性不检查行为 | mock 验证迭代次数 |

**架构建议：**
- MCP server 的 `RAGPipeline.__new__()` 模式脆弱，每次加属性都会静默遗漏。建议改为 `RAGPipeline.from_existing()` 类方法或 `skip_index=True` 参数。

---

## 引用溯源（2026-05-25）✅

**目标：** 答案附带原文来源（文件名 + chunk 位置），用户可验证答案可信度

**设计文档：** `docs/superpowers/specs/2026-05-25-citation-design.md`
**实现计划：** `docs/superpowers/plans/2026-05-25-citation-plan.md`

**核心改造：** 将全链路的 `list[str]` 升级为 `list[Chunk]`，每个 chunk 携带 `text` + `doc_name` + `chunk_index`

**新增文件：**
- `rag/models.py` — `Chunk` 数据类（`frozen=True`，可哈希，支持 RRF 融合去重）

**改造文件（9 个）：**

| 文件 | 改动 |
|------|------|
| `rag/chunker.py` | 新增 `doc_name` 参数，返回 `list[Chunk]` |
| `rag/vector_store.py` | `add()` 存储 Chunk 元数据到 payload，`search()` 返回 `list[Chunk]` |
| `rag/retriever.py` | BM25 对 `c.text` 分词，RRF 用 Chunk 作 dict key |
| `rag/reranker.py` | 提取 `c.text` 调 API，保留 Chunk 对象返回 |
| `rag/memory.py` | SYSTEM_PROMPT 增加引用指令，`build_messages()` 格式化 `[N] doc_name(第M段): text` |
| `rag/pipeline.py` | `QueryResult` 增加 `sources` 字段，提取 `doc_name` 传入 chunker |
| `rag/agent.py` | retrieve 工具返回带来源标注的文本 |
| `rag/gui.py` | 答案下方折叠展示来源列表 |
| `tests/test_chunker.py` | 移除重复测试 |

**代码审查修复：**
- gui.py: 移除重复 `subprocess.run(cmd)`（Important）
- memory.py: `hasattr` 鸭子类型改为 `isinstance(c, Chunk)` 类型检查（Important）
- test_chunker.py: 移除重复测试（Minor）

**实现过程（TDD，11 个 Task）：**

| Task | 内容 | 提交 |
|------|------|------|
| 1 | Chunk 数据类 | `6881535` |
| 2 | chunker 返回 Chunk | `a48629f` |
| 3 | vector_store 存储/检索元数据 | `2fb8a9e` |
| 4 | retriever 适配 Chunk | `d7e1545` |
| 5 | reranker 适配 Chunk | `4a27059` |
| 6 | build_messages 格式化来源 | `21e0742` |
| 7 | pipeline 全链路 Chunk + sources | `3cad516` |
| 8 | agent retrieve 工具适配 | `1358d16` |
| 9 | GUI 展示来源 | `6383d70` |
| 10 | e2e 测试 + 全量回归 | — |
| 11 | 代码审查 + 推送 | `888f38c` |

**测试：** 82 个测试全过（原 71 + 新增 11，含 1 个重复测试清理）

**改造效果示例：**

用户问"服务间超时怎么配？"，回答变为：
> 根据文档[1]，服务间调用超时默认为 3 秒[2]。

答案下方展示来源：
> **[1]** 运维手册.md — 第3段
> **[2]** 运维手册.md — 第7段

## 未来计划总览（2026-05-25）

**路线图：** 先做检索质量优化，再做 Agent 能力，最后打包 AiPy

| Task | 名称 | 状态 | 前置依赖 |
|------|------|------|---------|
| 15 | 查询改写 | ✅ 完成 | 无 |
| 16 | HyDE 假设文档嵌入 | ⏳ 待定 | Task 15 效果评估后决定 |
| 17 | 领域同义词词典 | ⏳ 待定 | 根据实际场景决定 |
| 18 | 引用溯源 | ✅ 完成 | 无 |
| 19 | Agent 化改造 | ✅ 完成 | 无 |
| 20 | 包装为 AiPy Pro 智能体 | ✅ 完成 | 无 |

**核心原则：** 每一步都根据实际效果决定下一步，不盲目堆功能

## Prompt 修复与兼容性（2026-05-25）

| 问题 | 原因 | 解决 |
|------|------|------|
| LLM 翻译项目名称（Hugging Face→拥抱脸，Ollama→奥拉马） | SYSTEM_PROMPT 规则太笼统 | 增加"项目名称、人名不翻译"+ 具体反例 |
| 查询失败 400 "在思考模式下必须返回给API" | DeepSeek v4-flash 默认启用 thinking mode，返回 `reasoning_content` 字段导致 API 400 | `generate()` 添加 `extra_body={"thinking": {"type": "disabled"}}` 显式关闭 thinking mode + 过滤 messages 只保留 `role` + `content` |

**修改文件：**
- `rag/memory.py` — SYSTEM_PROMPT 增加项目名/人名不翻译规则 + 反例
- `rag/generator.py` — 过滤 `reasoning_content` 字段

**待测试：** 用户下次启动 GUI 验证修复效果

## 计划书合并与文档清理（2026-05-25）

**目标：** 将分散的设计文档和实现计划合并为一份统一的计划书，删除冗余文件。

**合并内容：**
- 原 `rag-system-plan.md` 阶段二~四的功能点展开为 5 个详细 Task（21~25）
- 每个 Task 包含：架构设计、数据模型、核心代码、API 端点、TDD 步骤、面试话术
- 新增 Task 10.5：Excel 解析（openpyxl）
- 新增 Task 26：反馈闭环、Task 27：部署就绪

**删除文件（7 个）：**

| 文件 | 原因 |
|------|------|
| `specs/2026-05-20-rag-system-design.md` | 内容已在主计划书技术栈部分 |
| `specs/2026-05-23-multi-turn-memory.md` | Task 12 已在主计划书 |
| `specs/2026-05-23-rerank-design.md` | Task 13 已在主计划书 |
| `specs/2026-05-24-agent-design.md` | Task 19 已在主计划书 |
| `plans/2026-05-24-agent-plan.md` | Task 19 已在主计划书 |
| `specs/2026-05-25-citation-design.md` | Task 18 已在主计划书 |
| `plans/2026-05-25-citation-plan.md` | Task 18 已在主计划书 |

**保留文件（4 个）：**
- `plans/rag-system-plan.md` — 主计划书（合并版，Task 1~27）
- `plans/dev-log.md` — 开发日志（本文件）
- `demo-文档.md` — 测试文档
- `aipy-pro-deploy.md` — AiPy 部署文档

**计划书结构：** 扁平 Task 列表（1~27），每个 Task 标注阶段标签（阶段一~四），取消阶段分组章节。

## Task 10.5：Excel 解析（2026-05-25）✅

**目标：** 支持 `.xlsx` 文档加载，覆盖企业常见的 Excel 数据格式。

**实现：**
- `rag/loader.py` 新增 `load_excel()` 函数，用 `openpyxl` 读取所有 sheet，按行转 tab 分隔文本
- `load()` 分发逻辑加入 `.xlsx` 扩展名
- `rag/gui.py` 上传类型加入 `xlsx`
- 损坏文件处理：try/except 包装为 `ValueError`，用户友好错误信息

**TDD 流程：**

| 步骤 | 内容 | 结果 |
|------|------|------|
| RED | 写 3 个失败测试（正常/多 sheet/空文件） | 3 FAILED: ValueError 不支持的文件格式 |
| GREEN | 实现 `load_excel()` + `load()` 分发 | 8 PASSED |
| REFACTOR | — | — |

**代码审查修复（3 个 Important）：**

| Issue | 修复 |
|-------|------|
| 空文件测试断言太弱（只检查 `isinstance`） | 改为 `assert "=== Sheet:" in result` |
| 损坏文件无错误处理 | `load_excel()` 加 try/except → `ValueError` + 新增 `test_load_excel_corrupt_file` |
| query_rewriter `extra_body` 无测试保护 | 新增 `test_rewrite_query_disables_thinking_mode` |

**测试：** 87 个全过（原 82 + 新 5）

## query_rewriter 重构：消除重复 API 调用（2026-05-25）

**问题：** `query_rewriter.py` 和 `generator.py` 各自直接调用 DeepSeek API，thinking mode fix 要加两处。漏一处就出 400 错误（用户实际遇到过两次）。

**根因：** 多处直接调用 API，没有统一入口。

**解决：** `query_rewriter.py` 不再直接调 API，改为复用 `generator.generate()`。

**架构变化：**

```
之前（两处直接调 API，fix 要加两次）：
  generator.py      → OpenAI client → API (有 fix)
  query_rewriter.py → OpenAI client → API (有 fix)

现在（单一入口，fix 只维护一处）：
  generator.py      → OpenAI client → API (有 fix)
  query_rewriter.py → generate() ───┘
  agent.py          → generate() ───┘
  memory.py         → generate() ───┘
```

**改动：**
- `rag/query_rewriter.py` — 删除 `_client`、`_get_client()`、直接 API 调用，改为 `from rag.generator import generate`
- `tests/test_query_rewriter.py` — 重写 5 个测试，mock `rag.generator.generate` 而非 `_get_client`

**测试：** 87 个全过

**教训：** 新增 LLM 调用时，必须复用 `generate()` 而非自己创建 client。这是避免重复 fix 的根本方案。以后加新功能需要调 LLM 时，直接用 `generate()` 就行，不会漏掉 fix。

## Agent 模块 thinking mode 修复（2026-05-25）

**问题：** GUI 中简单问题正常，复杂问题报 400 "在思考模式下必须返回给API"

**根因：** 简单问题走 RAG 路径（调 `generate()`，有 thinking mode fix），复杂问题走 Agent 路径（调 LangChain `ChatOpenAI`，**没有** `extra_body`）。

**修复：** `rag/agent.py` 的 `ChatOpenAI` 构造函数添加 `model_kwargs`：

```python
self.llm = ChatOpenAI(
    model=settings.deepseek_model,
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
    temperature=0.3,
    model_kwargs={"extra_body": {"thinking": {"type": "disabled"}}},
)
```

**新增测试：** `test_agent_disables_thinking_mode` — 验证 `ChatOpenAI` 接收到正确的 `model_kwargs`

**测试：** 88 个全过

**教训总结 — thinking mode 防护体系：**

| 场景 | 调用路径 | 防护方式 |
|------|---------|---------|
| 查询改写、生成回答 | `generate()` | `generate()` 内置 `extra_body` |
| LangChain Agent | `ChatOpenAI` | `model_kwargs={"extra_body": {"thinking": {"type": "disabled"}}}` |
| 新增 LLM 调用 | 必须走 `generate()` | 不允许自行创建 OpenAI client |

**根本原则：** 所有 LLM 调用必须通过 `generate()` 进行（agent.py 是唯一例外，因为 LangChain 框架要求 `ChatOpenAI` 对象）。

## Task 24：评估系统（2026-05-26）✅

**目标：** 自动化评估 RAG 系统质量，用 Hit Rate 和延迟两个指标驱动参数调优。

**新增文件：**
- `rag/eval.py` — 评估模块（EvalResult 数据类 + 4 个核心函数 + CLI 入口）
- `data/eval_dataset.jsonl` — 11 题评估数据集（基于 Task 14 CloudNova 测试）
- `tests/test_eval.py` — 7 个测试（含 CLI 测试）

**核心函数：**

| 函数 | 功能 |
|------|------|
| `load_dataset(path)` | 加载 JSONL 测试集 |
| `evaluate(pipeline, dataset)` | 运行 pipeline 并记录命中/延迟 |
| `compute_metrics(results)` | 计算 Hit Rate、平均延迟、通过/失败数 |
| `print_report(results, metrics)` | 格式化打印评估报告 |

**指标：**
- Hit Rate：答案中包含期望关键词的比例
- 平均延迟：每次查询的平均耗时（ms）

**CLI 使用：**
```bash
python -m rag.eval --dataset data/eval_dataset.jsonl --file docs/demo-文档.md
```

**评估历史：** 每次运行自动追加到 `data/eval_history.jsonl`（含时间戳、参数、指标），便于对比不同参数配置的效果。

**TDD 流程：**

| 步骤 | 内容 | 结果 |
|------|------|------|
| RED | 6 个失败测试（load/evaluate/metrics） | 6 FAILED: ModuleNotFoundError |
| GREEN | 实现 `rag/eval.py`（4 函数 + CLI） | 6 PASSED |
| 代码审查 | 修复 CLI 入口 + 补 CLI 测试 | 7 PASSED |

**测试：** 95 个全过（原 88 + 新 7，含 CLI 测试）

**代码审查修复（1 Important）：**

| Issue | 级别 | 修复 |
|-------|------|------|
| CLI 入口路径错误（`python -m rag.eval` 不会触发 `__main__.py`） | Important | 删除 `__main__.py`，将 CLI 入口移到 `eval.py` 的 `main()` + `if __name__` |
| CLI 无测试覆盖 | Important | 新增 `test_cli_main` 验证 history 文件写入 |

**首次评估结果：**

```
评估报告: 10/11 通过 (Hit Rate: 90.9%)
平均延迟: 7116ms
```

| # | 问题 | 结果 |
|---|------|------|
| 1 | NovaRegistry 使用什么一致性协议？ | ✅ |
| 2 | 灰度发布分几个阶段？ | ✅ |
| 3 | mTLS 的三种配置模式是什么？ | ✅ |
| 4 | 熔断后多久进入 HALF-OPEN 状态？ | ✅ |
| 5 | 日志保留策略中 ERROR 日志保留多久？ | ✅ |
| 6 | 服务间调用超时怎么排查？ | ✅ |
| 7 | 如何保证配置下发的安全性？ | ❌ |
| 8 | 错误码 2001 是什么意思？ | ✅ |
| 9 | 限流规则的分布式模式基于什么实现？ | ✅ |
| 10 | 服务挂了怎么自动摘除？ | ✅ |
| 11 | 怎么防止某个服务把集群资源吃光？ | ✅ |

**分析：**
- Hit Rate 90.9%，较 Task 14 手动测试的 82% 提升 9 个百分点
- Q10 之前失败现在通过（查询改写生效：口语"服务挂了"→ 正式"健康检查"）
- Q7 失败属预期内：文档未显式关联"配置下发"与"mTLS"，需跨章节推理，RAG 固有局限
- 平均延迟 7.1s/题，正常范围（每题走完整 pipeline：改写→检索→重排序→生成）

## Task 21：基本鉴权（2026-05-26）✅

**目标：** API Key 认证，最小可用的鉴权方案，支持配置开关和多用户隔离。

**新增文件：**
- `rag/auth.py` — FastAPI Security 依赖注入（`verify_api_key` 函数）
- `tests/test_auth.py` — 6 个测试

**修改文件：**
- `config.py` — 新增 `auth_enabled`（默认 False）、`auth_keys`（JSON 格式）
- `rag/api.py` — `/index` 和 `/query` 端点注入 `Security(verify_api_key)`，中文接口描述

**鉴权逻辑：**
- `auth_enabled=False`（默认）→ 跳过校验，返回 "anonymous"
- `auth_enabled=True` → 检查 `X-API-Key` Header，匹配成功返回 `user_id`，否则 401/403

**配置方式：**
```bash
RAG_AUTH_ENABLED=true
RAG_AUTH_KEYS={"admin": "sk-admin-xxx", "user1": "sk-user-xxx"}
```

**TDD 流程：**

| 步骤 | 内容 | 结果 |
|------|------|------|
| RED | 6 个失败测试 | 6 FAILED: ModuleNotFoundError |
| GREEN | 实现 `rag/auth.py` | 6 PASSED |
| 集成 | api.py 注入 Depends | 全量回归通过 |

**测试：** 101 个全过（原 95 + 新 6）

**代码审查修复（2 Important）：**

| Issue | 级别 | 修复 |
|-------|------|------|
| `Depends` 应改为 `Security` 以正确生成 OpenAPI 安全方案 | Important | api.py 中 `Depends(verify_api_key)` → `Security(verify_api_key)` |
| `json.loads` 配置格式错误会抛未处理异常 | Important | auth.py 加 `try/except json.JSONDecodeError` → 500 |

**中文本地化：**
- API 标题：RAG 知识库 API
- 端点描述：健康检查 / 索引文档 / 查询知识库
- 错误信息全部中文（401 缺少 Key、403 Key 无效、413 文件过大、500 配置错误）

**手动测试脚本：** `test_auth.py` — 7 个场景全过（健康检查、无 Key 401、错误 Key 403、正确 Key 通过、索引鉴权）

## Task 22：多知识库管理（2026-05-26）✅

**目标：** 支持多个隔离的知识库，不同部门/项目数据互不可见。

**新增文件：**
- `rag/knowledge_base.py` — KnowledgeBaseManager（创建/列表/删除知识库 + 添加/删除文档）
- `tests/test_knowledge_base.py` — 6 个测试

**修改文件：**
- `rag/vector_store.py` — 新增 `add_to_collection` / `search_collection` / `delete_doc`，支持指定 collection
- `rag/api.py` — 新增 5 个端点（列出/创建/删除知识库 + 添加/删除文档）
- `tests/test_vector_store.py` — 新增 5 个测试

**API 端点：**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/knowledge-bases` | 列出所有知识库 |
| POST | `/knowledge-bases` | 创建知识库 |
| DELETE | `/knowledge-bases/{kb_id}` | 删除知识库 |
| POST | `/knowledge-bases/{kb_id}/documents` | 添加文档到知识库 |
| DELETE | `/knowledge-bases/{kb_id}/documents/{doc_name}` | 删除文档 |

**TDD 流程：**

| 步骤 | 内容 | 结果 |
|------|------|------|
| RED | vector_store 5 个失败测试 | 5 FAILED: ImportError |
| GREEN | 实现 add_to_collection/search_collection/delete_doc | 10 PASSED |
| RED | knowledge_base 6 个失败测试 | 6 FAILED: AttributeError |
| GREEN | 实现 KnowledgeBaseManager | 6 PASSED |
| 集成 | api.py 新增 5 个端点 | 全量回归通过 |

**测试：** 112 个全过（原 101 + 新 11）

## Task 22 代码审查修复（2026-05-26）

**3 个 Critical 问题修复：**

| # | 问题 | 修复 |
|---|------|------|
| 1 | `list_kbs()` 返回所有 collection（含 `rag_docs`） | 添加 `if not c.name.startswith("kb_"): continue` 过滤 |
| 2 | `delete_kb()` 无安全防护，可删除系统集合 | 添加 `if not kb_id.startswith("kb_"): raise ValueError` 校验 |
| 3 | KB 只能写入不能查询（`RAGPipeline` 不支持 `kb_id`） | `Retriever` 新增 `collection_name` 参数，`RAGPipeline` 新增 `kb_id` 参数，`KnowledgeBaseManager` 新增 `search()` 方法 |

**新增 API 端点：**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/knowledge-bases/{kb_id}/query` | 对指定知识库进行语义检索 |

**新增测试（7 个）：**
- `test_list_kbs_filters_non_kb_collections` — 验证过滤非 kb_ 前缀集合
- `test_delete_kb_rejects_non_kb_prefix` — 验证拒绝删除系统集合
- `test_delete_kb_allows_kb_prefix` — 验证允许删除 kb_ 前缀集合
- `test_search_returns_chunks` — 验证 KnowledgeBaseManager.search()
- `test_retrieve_with_collection_name_uses_search_collection` — 验证 Retriever 使用指定 collection
- `test_pipeline_with_kb_id_skips_indexing` — 验证 Pipeline 有 kb_id 时跳过索引
- `test_query_knowledge_base` — 验证 API 端点

**测试：** 119 个全过（原 112 + 新 7）

### 第二轮代码审查修复（2026-05-26）

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | Critical | `RAGPipeline(kb_id=...)` 仍调用 `clear()`/`add()` 污染全局 `rag_docs` | 当 `kb_id` 存在时跳过索引，KB 数据已通过 `add_document()` 写入 |
| 2 | Critical | `delete_kb` API 捕获所有异常返回 404，安全防护的 `ValueError` 被吞掉 | 分别捕获 `ValueError` → 403、其他异常 → 404 |
| 3 | Important | `delete_kb` 不检查集合是否存在 | 添加 `collection_exists()` 检查 |
| 5 | Important | API 端点无 403 错误测试 | 新增 `test_delete_system_collection_returns_403` |

**测试：** 120 个全过（原 119 + 新 1）

### GUI 知识库管理界面（2026-05-27）

**新增功能：** 侧边栏 📚 知识库管理区域

| 功能 | 说明 |
|------|------|
| 创建知识库 | 输入名称，点"创建" |
| 列出知识库 | 显示所有 KB 及文档数量 |
| 上传文档到 KB | 选择目标 KB，上传文件 |
| 查询 KB | 选择 KB，输入问题，查看结果 |
| 删除 KB | 点 🗑️ 按钮（删除 rag_docs 会报错） |

**新增测试（6 个）：** `tests/test_gui.py`

| 测试 | 验证 |
|------|------|
| `test_gui_create_kb` | 创建返回 kb_ 前缀 ID |
| `test_gui_list_kbs_shows_only_user_kbs` | 列表过滤系统集合 |
| `test_gui_delete_system_kb_raises` | 删除 rag_docs 抛 ValueError |
| `test_gui_upload_document_to_kb` | 上传走 load→chunk→embed→add |
| `test_gui_query_kb_returns_results` | 查询返回带元数据的 Chunk |
| `test_gui_delete_nonexistent_kb_raises` | 删除不存在 KB 抛 ValueError |

**测试：** 126 个全过（原 120 + 新 6）

### Qdrant 客户端共享修复（2026-05-27）

**问题：** `vector_store.py` 和 `knowledge_base.py` 各自维护独立的 `_client` 单例，指向同一个 `qdrant_data` 目录，导致锁冲突。

**修复：** `knowledge_base.py` 删除自己的 `_get_client()`，改为 `from rag.vector_store import _get_client`。

**意外事故：** `git checkout -- rag/vector_store.py` 撤销了未提交的多集合函数（`add_to_collection`、`search_collection`、`delete_doc`），导致测试 import 失败。手动恢复后提交。

**教训：** 重要改动要先提交，不要留作未提交状态。

### Task 22 多知识库代码审查修复汇总（2026-05-27）

**三轮审查共修复 8 个问题：**

| 轮次 | # | 级别 | 问题 | 修复 |
|------|---|------|------|------|
| 1 | 1 | Critical | `list_kbs()` 返回所有 collection | 添加 `kb_` 前缀过滤 |
| 1 | 2 | Critical | `delete_kb()` 可删除 `rag_docs` | 添加前缀校验 |
| 1 | 3 | Critical | KB 只能写不能查 | `RAGPipeline` + `Retriever` 支持 `kb_id` |
| 2 | 1 | Critical | `RAGPipeline(kb_id=...)` 污染全局集合 | 有 `kb_id` 时跳过索引 |
| 2 | 2 | Critical | `delete_kb` API 返回 404 而非 403 | 分别捕获 `ValueError` → 403 |
| 3 | 1 | Important | 显示名称截断（多词名称只显示第一词） | 从右侧去掉 `_hex` 后缀再取名 |
| 3 | 2 | Important | `add_to_collection` 静默创建任意集合 | 改为不存在时抛 `ValueError` |
| 3 | 3 | Important | 上传文件名显示为临时文件名 | `add_document` 新增 `doc_name` 参数 |

**GUI 知识库管理（2026-05-27）：**

| 功能 | 说明 |
|------|------|
| 创建知识库 | 输入名称，生成 `kb_slug_hex` 格式 ID |
| 列出知识库 | 显示 KB ID、文档数量 |
| 上传文档到 KB | 选择目标 KB，保留原始文件名 |
| 查询 KB | 选择 KB，输入问题，返回带来源的结果 |
| 删除 KB | 安全防护，拒绝删除系统集合 |

**新增测试（3 个独有覆盖）：**

| 测试 | 验证 |
|------|------|
| `test_delete_nonexistent_kb_raises` | 删除不存在 KB 抛 ValueError |
| `test_search_kb_empty_results` | 查询空 KB 返回空列表 |
| `test_add_to_collection_raises_if_not_exists` | 写入不存在集合抛 ValueError |

**测试：** 122 个全过

## ~~双门户架构设计与计划（2026-05-27）~~ 【废案】

> **状态：已废弃。** 双门户架构（admin_gui + user_gui）已从项目中移除，相关设计文档和计划文档已删除。当前项目采用 Web UI（static/index.html）+ FastAPI API 的单体架构。

**设计文档：** `docs/superpowers/specs/2026-05-27-dual-portal-design.md`（已删除）
**实现计划：** `docs/superpowers/plans/2026-05-27-dual-portal-plan.md`（已删除）

**核心决策：**
- 管理端 `admin_gui.py` + 用户端 `user_gui.py`，独立入口
- 管理端按钮驱动（按钮注册表模式），用户端纯聊天
- 用户端通过 FastAPI API 通信（`POST /query`），不直接导入模块
- AI 自主决策：数据处理/画图由大模型判断，不需用户手动选工具
- 登录系统记在计划里，后续实现

**扩展规则：每新增一个功能，管理端就多一个按钮。**

**实现计划（6 个 Task）：**

| Task | 内容 | 测试 |
|------|------|------|
| 1 | 按钮注册表 `button_registry.py` | 5 个 |
| 2 | 管理端侧边栏（上传 + KB 管理） | 3 个 |
| 3 | 管理端按钮栏 + 聊天 + 评估 + 鉴权 | 1 个 |
| 4 | 用户端纯聊天界面（API 调用） | 3 个 |
| 5 | `/query` 端点返回 sources | 1 个 |
| 6 | 全量回归 + 旧 GUI 弃用 | — |

**状态：** 计划已写好，实现留到其他功能完成后。

## Task 28：执行追踪日志（2026-05-27）✅

**目标：** 记录 Agent 调用链，出问题时可追溯路由决策、工具调用、耗时。

**新增文件：**
- `rag/tracker.py` — ExecutionTracker + ExecutionTrace + ToolCall 数据类
- `tests/test_tracker.py` — 5 个测试

**修改文件：**
- `rag/pipeline.py` — query() 保存 ExecutionTrace（路由、答案、耗时）
- `rag/gui.py` — 侧边栏新增"执行日志"展开区域
- `tests/test_pipeline.py` — 新增 `test_pipeline_saves_execution_trace`

**TDD 流程：**

| 步骤 | 内容 | 结果 |
|------|------|------|
| RED | 5 个失败测试（建表/保存/查询/空数据/JSON 序列化） | 5 FAILED |
| GREEN | 实现 `rag/tracker.py` | 5 PASSED |
| RED | 1 个 pipeline 集成测试 | 1 FAILED |
| GREEN | pipeline.py 集成 tracker | 13 PASSED |
| GUI | 侧边栏执行日志展示 | 128 PASSED |

**修复：** `:memory:` 数据库每次 `sqlite3.connect()` 创建新实例，tracker 改为持久连接。

**测试：** 128 个全过（原 122 + 新 6）

### Task 28 代码审查修复（2026-05-27）

**2 个 Important + 2 个 Minor 修复：**

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | Important | ToolCall 从未被填充，details 列始终为 "[]" | Pipeline 用 wrapper 包装 agent 工具的 func，捕获输入/输出/耗时 |
| 3 | Important | GUI 硬编码 `ExecutionTracker(db_path="memory.db")` | 改为 `st.session_state.pipeline.tracker` |
| 5 | Minor | gui.py 重复 `import os` | 移除重复 |
| 6 | Minor | gui.py 循环内 `import json` | 移除，用模块级 import |

**遗留（后续修复）：**
- Issue 2：ExecutionTracker 无 `close()` 方法，长时间运行会累积连接
- Issue 4：pipeline 集成测试可增加 tracker 初始化验证

**测试：** 129 个全过（原 128 + 新 1）

## 工业级加固设计（2026-05-29）

**设计文档：** `docs/superpowers/specs/2026-05-29-industrial-hardening-design.md`

**背景：** 面试反馈指出 4 个 🔴 级缺口——容错、安全、并发、指标。从 Demo 级升级到可上线的工业级。

**4 个子系统：**

| 子系统 | 核心机制 | 关键文件 |
|--------|---------|---------|
| 容错层 | 重试（指数退避）+ 熔断器（CircuitBreaker）+ 降级 + 超时控制 + 结果缓存 | `rag/resilience.py`（新建） |
| 安全层 | Prompt Injection 检测 + 输入净化 + 输出审查 + 速率限制 + 审计日志 | `rag/guard.py`（新建） |
| 并发层 | 读写锁 + 连接池 + 请求队列 + 健康检查 | `rag/concurrency.py`（新建） |
| 指标层 | 评估集扩充 30+ 题 + 回归检测 + 多维指标 + Bad Case 库 | `rag/eval.py`（修改） |

**实现顺序：** 容错 → 安全 → 并发 → 指标

**状态：** 设计已写好，实现计划待写。

## 当前项目状态总结（2026-05-29）

**已完成模块（18 个，Task 1~20 + 10.5 + 21 + 22 + 24 + 28 + 22 修复）：**
1. 文档加载（txt/md/pdf/docx/xlsx）
2. 文本分块（RecursiveCharacterTextSplitter + Chunk 元数据）
3. 嵌入模型（百炼 text-embedding-v4，批量处理）
4. 向量存储（Qdrant 本地模式，Chunk payload）
5. 混合检索（向量 + BM25 + RRF，Chunk 对象）
6. 重排序（百炼 gte-rerank API，Chunk 透传）
7. 生成（DeepSeek v4 flash，thinking mode 兼容）
8. 多轮对话记忆（SQLite + 自动摘要 + 来源格式化）
9. 查询改写（LLM 口语→正式，复用 generate()）
10. MCP 智能体扩展（DXT 打包，3 个工具）
11. Agent 化改造（LangChain ReAct + 4 工具 + Router）
12. 数据分析工具（calculate / sql_query / plot_chart / import_data）
13. 引用溯源（Chunk 数据类 + 全链路元数据传递 + 来源标注）
14. Excel 解析（openpyxl，所有 sheet 转文本）
15. 评估系统（Hit Rate + 延迟，JSONL 数据集，CLI 报告）
16. 基本鉴权（API Key 认证，FastAPI Security，配置开关）
17. 多知识库管理（Qdrant 多 collection，KnowledgeBaseManager，6 个 API 端点含查询）
18. 执行追踪日志（SQLite 记录调用链，GUI 侧边栏展示）

**待做模块（9 个）：**

| Task | 名称 | 优先级 | 复杂度 |
|------|------|--------|--------|
| 16 | HyDE 假设文档嵌入 | 中 | 中 |
| 17 | 领域同义词词典 | 低 | 高 |
| 23 | 双门户架构 | 中 | 中（计划已写好） |
| 25 | 监控与日志 | 中 | 中 |
| 26 | 反馈闭环 | 低 | 中 |
| 27 | 部署就绪 | 低 | 中 |
| 29 | 危险操作确认 | 中 | 低 |
| 30 | 并发安全 | 高 | 中（计划已写好） |
| 31 | 工业级加固 | 高 | 高（设计已写好） |

**架构说明：**
- 管理端（当前系统）：完整功能，含 Agent + 工具 + 执行追踪 + 危险确认
- 用户端（待做）：精简问答界面，只提问、不上传、不看日志
- 工业级加固（待做）：容错 + 安全 + 并发 + 指标

**测试：** 129 个全过

## 需求讨论：执行追踪 + 危险操作确认（2026-05-26）

**讨论背景：** 用户提出三个核心概念：

1. **ReAct + 路由** — 大模型自主决策调用哪个工具，Router 分流 RAG/Agent（已有）
2. **监控** — 调用 Agent/Tool 前后记录到数据库，出问题时排查（新增 Task 28）
3. **人工介入确认** — 危险操作加确认机制，防止误操作（新增 Task 29）

**结论：**
- 两个新功能都是管理端功能
- 用户端只需精简问答界面（记录需求，后续再做）
- 计划书新增 Task 28（执行追踪日志）和 Task 29（危险操作确认）

**测试：** 120 个全过

**可交付物：**
- 完整 RAG 系统（`rag/` 包 + `config.py`）
- Agent 模块（`rag/agent.py` + `rag/tools.py`）
- 评估系统（`rag/eval.py` + CLI + JSONL 数据集）
- API 鉴权（`rag/auth.py`，FastAPI Security，配置开关）
- 多知识库管理（`rag/knowledge_base.py`，Qdrant 多 collection，6 个 API 端点）
- 执行追踪日志（`rag/tracker.py`，SQLite 调用链记录，GUI 侧边栏展示）
- Streamlit GUI（`rag/gui.py`，文档上传 + 数据导入 + 来源展示 + 执行日志）
- FastAPI 后端（`rag/api.py`，含 API Key 鉴权 + 知识库端点）
- 双门户架构设计（`docs/superpowers/specs/2026-05-27-dual-portal-design.md`）
- 工业级加固设计（`docs/superpowers/specs/2026-05-29-industrial-hardening-design.md`）
- 工业级加固实现计划（`docs/superpowers/plans/2026-05-29-industrial-hardening-plan.md`，12 个任务）
- 测试文档 + 自动化测试脚本（`scripts/`）
- 统一计划书（`docs/superpowers/plans/rag-system-plan.md`）
- 129 个单元/集成测试全过

## 工业级加固实现完成（2026-05-29）

**实现内容：**
| 子系统 | 模块 | 核心功能 |
|--------|------|----------|
| 容错层 | resilience.py | 重试（指数退避）、熔断器（三态机）、结果缓存（TTL） |
| 安全层 | guard.py | Prompt Injection 检测、输入净化、输出审查 |
| 并发层 | concurrency.py | 读写锁（并发读、独占写） |
| 指标层 | eval.py | P95 延迟、Bad Case 归档 |

**集成点：**
- generator: 重试 + 熔断 → API 挂了不崩溃
- reranker: 重试 + 降级 → 跳过重排序用原始结果
- embedder: 重试 → 网络抖动自动恢复
- vector_store: 读写锁 → 多用户并发安全
- pipeline: guard → 注入攻击被拦截
- api: /health → 组件状态可观测
- eval: P95 + Bad Case → 优化效果可量化

**测试：** 157 个全过

## 工业级加固实现计划（2026-05-29）

**背景：** 面试反馈指出 4 个 🔴 级缺口——容错、安全、并发、指标。设计文档通过后，编写了 12 个任务的实现计划。

**计划结构：**
| 子系统 | 任务 | 核心内容 |
|--------|------|----------|
| 容错层 | Task 1-4 | 重试装饰器、熔断器、结果缓存、集成到 pipeline |
| 安全层 | Task 5-6 | Prompt Injection 防护（guard.py）、集成到 pipeline |
| 并发层 | Task 7-9 | 读写锁、vector_store 集成、健康检查 |
| 指标层 | Task 10-12 | 评估数据集扩充（30+题）、回归检测+Bad Case、全量回归 |

**技术方案：**
- 重试：指数退避 + 随机抖动，区分可重试/不可重试错误
- 熔断：CLOSED→OPEN→HALF_OPEN 状态机，连续 5 次失败触发
- 缓存：问题 hash 为 key，5 分钟 TTL
- Guard：关键词 + 模式 + 长度三层检测，输出审查
- 读写锁：`threading.RLock` 保护 Qdrant 写操作
- 评估：Hit Rate + 延迟 P50/P95 + Token 消耗 + 缓存命中率

**文件：** `docs/superpowers/plans/2026-05-29-industrial-hardening-plan.md`

## 工业级加固代码审查修复（2026-05-29）

**审查结果：** 2 Critical + 9 Important + 4 Minor

**修复内容：**

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | Critical | `ReadWriteLock.write()` yield 在 with 块外，并发写无互斥 | yield 移入 with 块内 |
| 2 | Critical | `CircuitBreaker` half_open 状态放行所有请求 | 新增 `_probe_admitted` 标志，只放一个探测请求 |
| 3 | Important | `check_output()` 混合大小写（如"System Prompt"）检测到但未替换 | 改用 `re.sub(..., flags=re.IGNORECASE)` |
| 4-5 | Important | `ResultCache` 无线程安全 + 无大小限制 | 加 `threading.Lock` + `max_size=1000` 淘汰最旧条目 |
| 6 | Important | `query_rewriter.py` 未集成 retry | 加 `@retry(max_attempts=2)` |
| 7 | Important | `save_bad_case()` 已实现但从未被调用 | `eval main()` 中对失败用例自动归档 |
| 8 | Important | `print_report()` 缺少 P95 延迟输出 | 新增 P95 行 |
| 9 | Important | reranker 超时 30s，规范要求 5s | `timeout=30` → `timeout=5` |
| 10 | Important | 缺写互斥测试 | 新增 `test_read_write_lock_enforces_write_mutual_exclusion` |

**未修复项：**
- Important #11（health check 硬编码 memory.db）：全代码库统一使用默认路径，保持一致性
- Minor #12-15：输出过滤模式窄、注入模式存储大小写、embedder 无熔断、import 位置

**测试：** 158 个全过（+1 新增写互斥测试）

## 面试要点逐条审查（2026-05-29）

**来源：** 面试反馈 4 条要点逐条对照

### 已覆盖（✅）
并发安全、多层缓存、召回率/排序率、短时/长时记忆、冒烟/回归测试、Bad Case 迭代、硬性指标（Hit Rate + P95）、重试/fallback、评估测试集、可观测性、稳定性、安全性、Prompt Injection、测试集、切分策略、多格式来源、多用户并发、为什么用 Qdrant

### 待补（⚠️ 本次讨论）
| 缺口 | 说明 |
|------|------|
| 缓存穿透/雪崩 | 有基础缓存，缺多级缓存 + 布隆过滤器 + 热点 key 保护 |
| 反思机制 | Agent 有 ReAct 但没有自我纠错重试 |
| 数据清洗 | 只有控制字符清理，没有完整 ETL |
| Prompt 管理 | 有 prompt 但没有版本化 + A/B 测试 + 回滚 |
| 性能测试 | 没有压测数据（并发数/吞吐量/P99 延迟） |

### 未覆盖（❌ 暂不做）
部署上线、知识图谱、语音交互、多模态、LoRA 微调、领域同义词消歧

## 阶段五实现完成：反思、缓存、清洗、Prompt 管理（2026-05-29）

**目标：** 补齐面试反馈中的 4 个 ⚠️ 缺口

**实现过程（TDD，9 个 Task，subagent-driven）：**

| Task | 内容 | 提交 |
|------|------|------|
| 1 | 工具级反思 — _wrap_tool_with_reflection() | `99b4f12` |
| 2 | 答案级自检 — _check_answer_quality() + run() 反思循环 | `4b0e230` |
| 3 | 缓存加固 — BloomFilter + TTL jitter + hot key | `adc6fe1` |
| 4 | 缓存集成到 pipeline | `3430773` |
| 5 | 数据清洗 — cleaner.py（编码/清理/去重/元数据） | `ace6872` |
| 6 | 清洗集成到 loader + pipeline | `9a226ae` |
| 7 | PromptManager + 4 个 YAML 文件 | `92b4209` |
| 8 | PromptManager 集成到 query_rewriter + agent | 工作树 |
| 9 | 全量回归 + 文档更新 | 本文档 |

**新增文件：**
- `rag/cleaner.py` — 数据清洗管道
- `rag/prompt_manager.py` — Prompt 版本管理器
- `prompts/rewrite.yaml` — 查询改写 prompt
- `prompts/router.yaml` — 路由判断 prompt
- `prompts/agent_system.yaml` — Agent 系统提示
- `prompts/quality_check.yaml` — 答案自检 prompt
- `tests/test_cleaner.py` — 18 个清洗测试
- `tests/test_prompt_manager.py` — 8 个管理器测试

**修改文件：**
- `rag/agent.py` — 工具反思包装 + 答案自检 + PromptManager 集成
- `rag/resilience.py` — BloomFilter + ResultCache 增强
- `rag/pipeline.py` — 缓存集成 + 段落去重
- `rag/loader.py` — 编码检测 + 文本清洗
- `rag/query_rewriter.py` — PromptManager 集成
- `tests/test_agent.py` — 5 个新测试
- `tests/test_resilience.py` — 7 个新测试

**测试：** 196 个全过（原 158 + 新 38）

## Task 36：性能压测（2026-05-29）✅

**目标：** 用 locust 对 API 端点进行并发压测，获取 QPS、延迟分布、错误率等面试可展示的性能数据。

**工具选型：** locust（Web UI + headless 模式，Python 脚本定义用户行为）

**新增文件：**
- `scripts/locustfile.py` — locust 用户行为（query + health check，权重 5:1）
- `scripts/run_benchmark.py` — 一键压测脚本（启动 server → 索引文档 → locust 压测 → 输出报告）

**修复：**
- `rag/tracker.py` — SQLite 线程安全问题（`check_same_thread=False`），压测时发现多线程并发写入 SQLite 报错

**压测结果（3 并发用户，30 秒）：**

```
============================================================
 RAG API 性能压测报告
============================================================
 并发用户数:  3
 持续时间:    30s
 总请求数:    55
 失败请求数:  0
 错误率:      0.0%
 QPS:         1.9
------------------------------------------------------------
 延迟分布 (Aggregated):
   Avg:   327 ms
   P50:   3 ms
   P95:   3200 ms
   P99:   6600 ms
------------------------------------------------------------
 按接口:
   /health                      11 次, avg=5ms, fails=0
   /query                       44 次, avg=408ms, fails=0
============================================================
```

**分析：**
- P50=3ms → 缓存命中（ResultCache 生效），大部分请求走缓存
- P95=3.2s → LLM API 调用（DeepSeek v4 flash），非缓存请求的正常延迟
- P99=6.6s → 包含 Agent 路由的复杂查询（需多步推理 + 工具调用）
- 0 失败率 → 容错层（重试 + 熔断）在并发场景下工作正常
- QPS=1.9 → 受限于 LLM API 延迟，非系统瓶颈

**使用方式：**
```bash
python scripts/run_benchmark.py --users 10 --duration 60 --file docs/demo-文档.md
```

**提交：** `9ed8b12`

---

## 代码审查 & 修复（2026-05-29）

阶段五完成后进行全量代码审查，发现 2 个 Critical + 3 个 Important 问题，全部修复。

**Critical 问题：**

| 问题 | 文件 | 原因 | 修复 |
|------|------|------|------|
| `_wrap_tool_with_reflection` 是死代码 | agent.py:60 | 函数定义了但从未被调用，工具级反思完全不生效 | 在 `RAGAgent.__init__` 中用 `_wrap_tool_with_reflection` 包装所有工具 |
| Pipeline 去重丢弃相似度结果 | pipeline.py:37-47 | 调用了 `deduplicate_chunks` 但只用 `set()` 做精确匹配，SequenceMatcher 结果被丢弃 | 改用 `unique_texts = set(deduplicate_chunks(...))` 过滤 chunks |

**Important 问题：**

| 问题 | 文件 | 原因 | 修复 |
|------|------|------|------|
| 质量自检 JSON 解析失败时静默通过 | agent.py:154-157 | LLM 返回 markdown 围栏 JSON 时解析失败，默认返回 `"pass"` | 剥离 markdown 围栏后重试，仍失败则返回 `"fail"` |
| PromptManager 文件名子串匹配 | prompt_manager.py:18 | `name in fname` 会误匹配不相关文件 | 改为 `fname.startswith(name)` 前缀匹配 |
| BloomFilter 无线程安全 | resilience.py:80-91 | `add()` 和 `__contains__` 操作 `bytearray` 无锁 | 添加 `threading.Lock` |

**留待后续：**
- 热点 key `get_stale_keys()` 未被消费 — 异步刷新机制不完整（安全但不符合设计文档）
- 工具级反思使用通用重试，未实现工具特定策略（如查询简化、跨工具降级）

**测试：** 196 个测试全过
**提交：** `8aa43cf`

**阶段五全部完成：** 4 个子系统（Agent 反思 + 缓存加固 + 数据清洗 + Prompt 管理）+ 性能压测，共 10 个 Task，196 个测试全过

---

## ~~双门户 + Docker 部署（2026-05-30）~~ 【废案】

> **状态：已废弃。** 双门户架构（admin_gui + user_gui）已从项目中移除。Docker 部署部分保留，但三服务架构（API + Admin + User）已废弃，当前采用 API 单服务 + Web UI 架构。

**目标：** 双门户架构（Admin + User）+ 容器化部署到 Render 免费层

**实现过程（7 个 Task，subagent-driven）：**

| Task | 内容 | 提交 |
|------|------|------|
| 1 | API /query 返回 sources | `e7b0f43` |
| 2 | User GUI（纯聊天界面，httpx 调 API） | `bed7d93` |
| 3 | Admin GUI（从 gui.py 迁移 + 兼容重定向） | `b5ce55d` |
| 4 | Dockerfile + .dockerignore | `1452b24` |
| 5 | start.sh（SERVICE_MODE 路由 + 自动索引） | `f178b9e` |
| 6 | docker-compose.yml + .env.example | `00478ee` |
| 7 | 更新计划书 + 全量测试 | 本文档 |

**新增文件：**
- `rag/admin_gui.py` — 管理端 GUI（从 gui.py 迁移，标题改为"RAG 管理端"）
- `rag/user_gui.py` — 用户端 GUI（纯聊天，httpx 调 API，无管理功能）
- `Dockerfile` — Python 3.12-slim + Java + pip 依赖
- `.dockerignore` — 排除 .git、缓存、运行时数据
- `start.sh` — SERVICE_MODE 路由 + 首次启动自动索引
- `docker-compose.yml` — 3 服务编排（API :8000 + Admin :8501 + User :8502）
- `.env.example` — 环境变量模板
- `tests/test_api_sources.py` — API sources 测试
- `tests/test_user_gui.py` — User GUI 测试

**修改文件：**
- `rag/api.py` — QueryResponse 新增 sources 字段
- `rag/gui.py` — 改为兼容重定向到 admin_gui.py

**部署架构：**
- 同一 Docker 镜像部署 3 次到 Render，通过 SERVICE_MODE 区分服务
- Admin 上传文档 → API 索引 → User 端实时可查
- 免费层：零成本，冷启动 30-50 秒

**测试：** 199 个全过（原 197 + 新 2）

### 部署代码审查修复（2026-05-30）

**审查结果：** 1 Critical + 5 Important，全部修复

| # | 级别 | 问题 | 文件 | 修复 |
|---|------|------|------|------|
| 1 | Critical | `data` 变量在 `try` 块外引用，异常路径 NameError | `rag/user_gui.py` | `messages.append` 移入 `try` 块内，使用已提取的 `answer`/`sources` 变量 |
| 2 | Important | start.sh 自动索引只扫 `*.md` + `*.txt`，漏掉 PDF/DOCX/XLSX | `start.sh` | glob 补上 `*.pdf`、`*.docx`、`*.xlsx` |
| 3 | Important | test_user_gui.py 断言 `or` 逻辑错误，永远通过 | `tests/test_user_gui.py` | `or` → `and` |
| 4 | Important | admin_gui.py 侧边栏标题仍是 "RAG 问答系统" | `rag/admin_gui.py` | 改为 "RAG 管理端" |
| 5 | Important | test_api_sources.py 纯 mock，无真实序列化测试 | `tests/test_api_sources.py` | 新增 `test_query_response_serialization` 验证 QueryResponse 模型 |
| 6 | Important | docker-compose.yml 无 healthcheck，GUI 可能在 API 就绪前启动 | `docker-compose.yml` | API 服务添加 curl healthcheck，GUI 改为 `condition: service_healthy` |

**测试：** 200 个全过（原 199 + 新增序列化测试）

## 启动性能优化（2026-05-30）

**问题：** API 启动耗时 5.77 秒，用户反馈"打开特别慢"。

**根因分析：** 模块级 import 链条导致启动时加载大量不需要的重型依赖。

```
api.py → pipeline.py → agent.py → tools.py → matplotlib (~1.5-3s)
                                     → openpyxl (~0.3-0.5s)
api.py → knowledge_base.py → loader/chunker/embedder/vector_store 全链路
```

**核心瓶颈：** `import matplotlib` 在 `tools.py` 顶层，通过 `pipeline.py → agent.py → tools.py` 链条拖慢所有入口。matplotlib 仅在 `plot_chart()` 函数内使用，启动时完全不需要。

**修复方案：** 6 个文件的模块级 import 改为函数内延迟导入。

| 文件 | 修改 |
|------|------|
| `rag/tools.py` | `import matplotlib` / `import openpyxl` 移入 `plot_chart()` / `import_data()` |
| `rag/agent.py` | `from rag.tools import ...` 移入 `create_agent_tools()` 和 `_parse_and_plot()` |
| `rag/pipeline.py` | `from rag.agent import RAGAgent, route_question` 移入 `__init__()` 和 `query()` |
| `rag/api.py` | `from rag.pipeline import RAGPipeline` 移入 `/index` 处理函数 |
| `rag/admin_gui.py` | `from rag.pipeline import RAGPipeline` 移入上传处理函数 |
| `rag/knowledge_base.py` | `loader/chunker/embedder/vector_store/qdrant_client` 全部移入各方法内部 |

**测试 patch 修复：** 延迟导入后，模块级名称不再存在，测试的 `@patch` 目标需改为源模块。

| 测试文件 | 旧 patch 目标 | 新 patch 目标 |
|----------|--------------|--------------|
| `tests/test_api.py` | `rag.api.RAGPipeline` | `rag.pipeline.RAGPipeline` |
| `tests/test_pipeline.py` | `rag.pipeline.route_question` | `rag.agent.route_question` |
| `tests/test_e2e.py` | `rag.pipeline.route_question` | `rag.agent.route_question` |
| `tests/test_knowledge_base.py` | `rag.knowledge_base._get_client` | `rag.vector_store._get_client` |
| `tests/test_knowledge_base.py` | `rag.knowledge_base.embed` | `rag.embedder.embed` |
| `tests/test_knowledge_base.py` | `rag.knowledge_base.chunk` | `rag.chunker.chunk` |
| `tests/test_knowledge_base.py` | `rag.knowledge_base.load` | `rag.loader.load` |
| `tests/test_gui.py` | 同上 | 同上 |

**效果：**

```
api.py 导入: 5.77s → 0.39s（提速 15 倍）
```

**测试：** 200 个全过

## 简化启动 + 文件夹自动索引（2026-05-30）

**背景：** 原系统启动 3 个服务（API + 管理端 + 用户端），Streamlit 启动慢，占用资源多。用户希望精简为只启动 API + 用户端，文件通过文件夹管理。

**改动：**
- 新增 `rag/folder_indexer.py`：`scan_folder()` 文件夹扫描 + `index_folder()` 全量索引
- 重写 `start_all.py`：启动时自动扫描 `data/upload/`，只启动 API + 用户端（2 个服务）
- 新增 `data/upload/` 数据目录
- 管理端代码保留，可手动启动

**设计文档：** `docs/superpowers/specs/2026-05-30-simplified-startup-design.md`

**效果：**
- 启动服务从 3 个减到 2 个
- 文件管理从 GUI 上传改为文件夹放置（`data/upload/`）
- 启动时自动全量索引，无需手动操作
- 支持 --data-folder 参数自定义数据目录
- 管理端保留，可手动启动：`streamlit run rag/admin_gui.py --server.port 8501`

**测试：** 7 个新测试全过（scan_folder 4 个 + index_folder 3 个）

### 启动问题排查与修复

**问题 1：folder_indexer 模块级 import 阻塞 5.64s**

| 原因 | 修复 |
|------|------|
| `folder_indexer.py` 顶层 import `rag.chunker`（3.81s）+ `rag.embedder`（0.56s），触发整个 import 链 | 改为函数内延迟加载（`import rag.loader as _loader`），模块级只保留轻量的 `SUPPORTED_EXTENSIONS` |

**效果：** folder_indexer import 5.64s → 0.03s

**问题 2：Streamlit 页面永远 "奔跑..." 加载不出来**

| 原因 | 修复 |
|------|------|
| `user_gui.py` 的 auto-launch 机制调用 `subprocess.run()` 阻塞脚本执行，Streamlit 永远等不到脚本完成 | `start_all.py` 启动 Streamlit 时设置 `_RAG_STREAMLIT=1` 环境变量，跳过 auto-launch |

**根因分析：** `user_gui.py` 设计为可独立运行（`python rag/user_gui.py`），auto-launch 会重新调用 `streamlit run`。但 `start_all.py` 已经用 `streamlit run` 启动了，auto-launch 再次触发导致 `subprocess.run()` 阻塞，脚本永远执行不完，页面永远停在 "奔跑..." 状态。

**测试：** 207 个全过

---

## GUI 美化 + API 自启动（2026-05-30）

### GUI 视觉美化

两个 GUI 原本使用 Streamlit 默认样式，无自定义 CSS。注入以下样式：

| 改动 | 说明 |
|------|------|
| Google Fonts | `Noto Sans SC`（中文）+ `Inter`（英文） |
| 侧边栏深色渐变 | `linear-gradient(180deg, #1e3a5f, #0f2744)` |
| 按钮渐变 + 悬停动效 | `translateY(-1px)` + `box-shadow` |
| Expander 卡片化 | 圆角 + 边框 + 微阴影 |
| 聊天气泡圆角 | `border-radius: 12px` |
| 管理端空状态 | 3 列卡片引导（上传/问答/来源） |
| 标题区域 | HTML 自定义标题 + 副标题 |

### API 自启动

**问题：** 管理端需要 API + Qdrant 才能运行，用户需要手动启动多个服务。

**方案：** 两个 GUI 的 `__main__` 块自动检测端口 8000，空闲则自动启动 uvicorn API 后台进程，退出时自动清理。

```
python rag/admin_gui.py   → 启动 API(8000) + 管理端(8501)
python rag/user_gui.py    → 启动 API(8000) + 用户端(8502)
```

**关键实现：**
- `_is_port_free()` 检测端口占用，避免重复启动
- `subprocess.Popen` 后台启动 uvicorn
- `atexit.register(api_proc.terminate)` 退出时自动清理
- 如果 API 已在运行，跳过启动步骤

---

## 目录结构规范化（2026-05-30）

### 问题

RAG 根目录散乱：start_all.py、run_eval.py、test_excel.xlsx、benchmark CSV 文件混在一起。RAGv2/RAGv3 有空的 docs/ 目录。

### 改动

**RAG：**
- 脚本 → `scripts/`（start_all.py、run_eval.py、start.sh）
- 评估数据 → `data/eval/`（eval_dataset.jsonl、eval_history.jsonl）
- 压测结果 → `benchmarks/`
- 删除临时文件（test_excel.xlsx、test_tmp.txt、memory.db）
- 更新路径引用：start_all.py PROJECT_ROOT、run_eval.py、rag/eval.py、Dockerfile

**RAGv2/RAGv3：**
- 新增 `prompts/`（4 个 YAML 模板）
- 删除空 `docs/`
- 新增 `history/.gitkeep`
- 更新 `.gitignore`

---

## Agent 图表显示问题（2026-05-30）

### 问题

用户请求画柱状图时，Agent 返回了文字描述的数据但 GUI 中图表显示为裂图（broken image）。

### 根因分析

代码审查发现多个问题叠加：

1. **LLM 未在回答中包含图表文件路径** — 系统提示只要求说"图表已生成"，未强制要求附上 `data/chart_xxx.png` 路径，DeepSeek 直接省略
2. **质量检查反射循环丢弃有效回答** — 如果自检认为回答太短（如"图表已生成，见 data/chart_xxx.png"），会重新提问，导致原图表路径丢失
3. **`os.path.exists` 使用相对路径** — Streamlit CWD 可能不是项目根目录，导致文件存在但检查失败
4. **DeepSeek 可能发送 JSON 格式工具输入** — 而非管道分隔字符串，`_parse_and_plot` 解析失败

### 已实施的修复

- `agent_system.yaml` v3：增加"禁止事项"强制要求调用工具 + 回答中包含文件路径
- `agent.py`：新增 `_extract_chart_paths()` 从工具输出中提取路径，自动注入到最终回答
- `agent.py`：`_parse_and_plot()` 增加 JSON 输入兼容
- `admin_gui.py`：`_is_chart_path()` 改用绝对路径检查

### 现状

修复后图表文件可以正常生成，但 Streamlit GUI 中 `st.image()` 显示为裂图。推测是 Streamlit 对生成的 PNG 文件路径处理有兼容性问题。

### 决策

**搁置此问题，留待网页版前端实现时统一解决。** 网页版可以用 `<img>` 标签直接引用文件路径，不存在 Streamlit 的兼容性问题。

---

## 代码审查修复（2026-05-30）

### 外部审查发现的问题

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | `api.py` `/health` 引用不存在的 `settings.memory_db_path` | Critical | ✅ 已修复 → `analysis_db_path` |
| 2 | `.env` 含真实 API key 被 git 追踪 | — | ❌ 误判：`.env` 在 `.gitignore` 中，从未 commit |
| 3 | RAGv2 零测试覆盖 | Important | 确认属实，RAGv2 无 tests/ 目录 |
| 4 | `cleaner.py` 用了 `chardet` 但 requirements.txt 未声明 | Important | ✅ 已修复：三个目录都补上 |
| 5 | `pipeline.py` 并发竞态条件 | — | ❌ 误判：有 `threading.Lock` 保护 wrap/unwrap |
| 6 | `folder_indexer.py` 重建集合后 BM25 索引过时 | Important | 确认属实，待修复 |
| 7 | `rag/__init__.py` 为空无公共 API | Medium | 确认属实，低优先级 |

**修复范围：** RAG、RAGv2、RAGv3 三个目录同步修复

---

## Agent 路由误判修复（2026-05-30）

### 问题

用户问"2025年发生了多少件重大安全事故"（纯事实查询），Router 误判为 Agent，Agent 自动生成了不需要的柱状图，且数据不完整（少了教育和政府两个行业）。

### 根因

1. **Router 过于激进** — "统计"、"多少"等词触发 Agent 路由，但这类词在事实查询中也很常见
2. **Agent 过于主动** — 即使用户没要求画图，Agent 也会自作主张调用 `plot_chart`
3. **retrieve top_k=5 不够** — 大表格数据被分到多个 chunk，5 条检索结果无法覆盖全部数据

### 修复

| 文件 | 版本 | 改动 |
|------|------|------|
| `router.yaml` | v3 | 重写路由规则：区分"问数据"（RAG）和"用数据做事"（Agent），增加关键区别示例 |
| `agent_system.yaml` | v4 | 限制自动画图：只有用户明确说了"画图"、"图表"等词才调用 plot_chart |
| `agent.py` | — | retrieve `top_k` 从 5 提升到 10，减少数据遗漏 |

### 验证

- "发生了多少件" → 路由到 RAG，不会画图 ✅
- "把XX画成柱状图" → 路由到 Agent，正确画图 ✅
- 207 个测试全过 ✅

---

## 第二轮代码审查修复（2026-05-30）

### 审查发现

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | `admin_gui.py` 缺少 sys.path 设置，Streamlit 子进程可能无法导入模块 | Critical | ✅ 已修复 |
| 2 | `agent.py` JSON 路径缺少 labels/values 空值保护 | Important | ✅ 已修复 |
| 3 | `agent.py` JSON 解析失败静默吞错 | Minor | ✅ 已修复 |

### 修复内容

- `admin_gui.py`：在 Streamlit 导入前添加 `_PROJECT_ROOT` 到 `sys.path`
- `agent.py` `_parse_and_plot()`：JSON 路径增加 `if not labels or not values` 守卫
- `agent.py` `_parse_and_plot()`：JSON 解析失败时返回明确错误而非静默跳过

**修复范围：** RAG、RAGv2、RAGv3 三个目录同步
**测试：** 207 个全过

---

## 图表中文字体修复（2026-05-30）

### 问题

Agent 生成的图表 PNG 文件中中文标签显示为方块（豆腐块），因为 matplotlib 默认不支持中文字体。

### 修复

在 `tools.py` 的 `plot_chart()` 函数中添加 matplotlib 中文字体配置：

```python
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
```

字体优先级：SimHei（黑体）→ Microsoft YaHei（微软雅黑）→ WenQuanYi Micro Hei（文泉驿）→ Arial Unicode MS（macOS）

**修复范围：** RAG、RAGv2、RAGv3 三个目录同步
**测试：** 207 个全过

---

## 第三轮代码审查修复 — 并发安全 & 安全加固（2026-05-31）

**来源：** 外部代码审查 RAGv2，发现 4 Critical + 7 Important + 9 Minor 问题

**验证结果：** 10 个问题全部确认属实，已修复

### Critical 修复

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| C1 | `CircuitBreaker` 无线程锁，多线程并发状态竞态 | `resilience.py` | 添加 `threading.Lock`，`record_failure`/`record_success`/`allow_request` 全部加锁 |
| C2 | `DialogueMemory` + `ExecutionTracker` SQLite 连接无锁 | `memory.py` + `tracker.py` | 添加 `threading.Lock`，所有 DB 操作加锁 + 新增 `close()` 方法 |
| C3 | `api.py` 全局 `pipeline` 变量读写无锁 | `api.py` | 添加 `_pipeline_lock`，`/index` 写入和 `/query` 读取均加锁 |
| C4 | `requirements.txt` 缺少 `requests`（`reranker.py` 依赖） | `requirements.txt` | 添加 `requests` |

### Important 修复

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| I1 | `import_data` 表名仅替换空格和连字符，特殊字符导致 SQL 注入 | `tools.py` | 改用 `re.sub(r"[^a-zA-Z0-9_一-鿿]", "_", raw_name)` |
| I2 | SQL 查询缺少分号检查，`SELECT 1; DROP TABLE x` 可绕过 | `tools.py` | 添加 `if ";" in sql.strip(): raise ValueError(...)` |
| I6 | Agent 运行异常时 `_unwrap_agent_tools()` 不执行，工具永久包装 | `pipeline.py` | 添加 `try/finally` 确保工具恢复 |
| I9 | `sanitize_input` 保留 `\r`（回车符），可能被用于注入 | `guard.py` | 移除 `c == "\r"`，`\r` 被 `ord(c) < 32` 过滤 |

### Minor 修复

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| M2 | `_extract_chart_paths` 对 Pydantic ToolCall 对象取 `.get()` 失败 | `agent.py` | 添加 `hasattr(tc, "content")` 分支处理 Pydantic 对象 |
| M7/M8 | `DialogueMemory` + `ExecutionTracker` 无 `close()` 方法 | `memory.py` + `tracker.py` | 添加 `close()` 方法 |

### 同步范围

所有修复同步到 RAG、RAGv2、RAGv3 三个目录

**测试：** 207 个全过

---

## ~~Chainlit 用户端 GUI（2026-06-01）~~ 【废案】

> **状态：已废弃。** Chainlit 用户端已从项目中移除。当前项目采用 Web UI（static/index.html）+ FastAPI API 架构。

**目标：** 用 Chainlit 替换 Streamlit 用户端，获得专业聊天界面 + 来源引用 + 思考链 + 反馈按钮。

**设计文档：** `docs/superpowers/specs/2026-05-31-chainlit-user-gui-design.md`

**新增文件：**
- `rag/user_gui_chainlit.py` — Chainlit 用户端主文件（~200 行）
- `tests/test_user_gui_chainlit.py` — 8 个测试

**修改文件：**
- `requirements.txt` — 添加 `chainlit` + 版本锁定所有依赖
- `scripts/start.sh` — `SERVICE_MODE=user` 改用 chainlit 命令
- `scripts/start_all.py` — 用户端改用 chainlit
- `rag/retriever.py` — BM25 空 chunks 防护
- `rag/chunker.py` — 从 settings 读取配置
- `rag/generator.py` — 处理 None 返回值
- `rag/tools.py` — SQL 注入增强 + 除零防护
- `Dockerfile` — 安装 curl（健康检查）

**核心设计（最终版）：**
- 通过 HTTP 调 FastAPI API（不直接导入 pipeline，避免 Qdrant 多进程冲突）
- 查询：`POST /query`
- 文件上传：`POST /index`
- 健康检查：`GET /health`
- 启动时自动索引 `data/upload/` 目录（通过 API）
- 独立启动：`python rag/user_gui_chainlit.py` 自动拉起 API + Chainlit

**踩坑记录：**
1. **Qdrant 多进程冲突** — 直接导入 RAGPipeline 时，API 进程和 Chainlit 进程同时访问 `qdrant_data`，报错"已被另一个 Qdrant 客户端实例访问"。解决方案：改为 HTTP API 调用
2. **BM25 ZeroDivisionError** — `RAGPipeline(kb_id="rag_docs")` 时 `chunks=[]`，`BM25Okapi([])` 内部除零。解决方案：`retriever.py` 空 chunks 时跳过 BM25 初始化
3. **Chainlit 子进程 sys.path 丢失** — Chainlit 通过 `chainlit run` 启动子进程，模块级 `sys.path` 设置可能不生效。解决方案：每个 lazy import 函数内都调 `_ensure_sys_path()`
4. **startup 代码 import 顺序** — `__main__` 块中 import `rag.folder_indexer` 前需要先设 `sys.path`
5. **pipeline 初始化失败不缓存** — 首次初始化失败后不能缓存 `None`，否则后续重试永远失败

**代码审查修复（2 Critical + 8 Important）：**
- C-1/C-2: 单例竞态 → `threading.Lock` 双重检查锁
- I-1: 文件大小限制 → 10MB 检查
- I-2: auth 时序攻击 → `hmac.compare_digest`
- I-3: `_get_pipeline` 阻塞事件循环 → `asyncio.to_thread`
- I-4: `on_chat_start` 缺 `await` → 补上
- I-5: `summarize_old_rounds` TOCTOU → 重新读取 total
- I-6: 测试只是存在性检查 → 补充行为测试
- I-7: pipeline 重建参数错误 → 用 `kb_id`
- I-8: KnowledgeBaseManager 连接泄漏 → 缓存单例

**测试：** 215 个全过
- `asyncio.to_thread()` 包装同步 pipeline.query（不阻塞 Chainlit 事件循环）
- 来源引用用 `cl.Text` 元素展示
- 文件上传用 `KnowledgeBaseManager.add_document()`（不清空旧数据）
- 鉴权通过 `CHAINLIT_AUTH` 环境变量控制
- 反馈按钮通过 `@cl.on_feedback` 回调处理

**Chainlit 相比 Streamlit 的优势：**
- 原生来源引用展示（不需要 expander hack）
- Agent 工具调用可视化（`cl.Step`）
- 内置反馈按钮（👍👎）
- 文件拖拽上传
- 图表不会裂图（用 `<img>` 标签）

**安装问题：** Python 3.12 下 `literalai` 的 `pkgutil.ImpImporter` 兼容问题，升级 setuptools 到 82.0.1 解决。

**测试：** 215 个全过

---

## ~~Chainlit 代码审查修复（2026-06-01）~~ 【废案】

> **状态：已废弃。** 随 Chainlit 用户端一同移除。

**审查发现：** 2 Critical + 5 Important

| 级别 | 问题 | 修复 |
|------|------|------|
| Critical | API 无 auth header，启用鉴权时 401/403 | 从 `RAG_API_KEY` 环境变量读取，所有请求加 `X-API-Key` header |
| Critical | `/index` 每次替换整个 pipeline，多文档上传丢失旧数据 | 改用 `KnowledgeBaseManager.add_document()`，累加而非替换 |
| Important | 用户上传无文件格式检查 | 添加 `.txt/.md/.pdf/.docx/.xlsx/.csv` 白名单 |
| Important | `session_id` 类型注解错误 | `str` → `Optional[str]` |

**测试更新：** `test_index_creates_pipeline` → `test_index_adds_to_kb`（mock KnowledgeBaseManager）

**测试：** 215 个全过

---

## 第四轮代码审查修复（2026-06-01）

**来源：** 用户自行审查，发现 6 Critical + 10 High + 19 Medium + 6 Low

**验证结果：** 部分审查有误（Dockerfile CMD、Docker 端口映射），实际修复 4 项

### 已修复

| 级别 | 问题 | 文件 | 修复 |
|------|------|------|------|
| Critical | `import_data` 列名未清洗，可 SQL 注入 | `tools.py` | `re.sub(r"[^a-zA-Z0-9_一-鿿]", "_", h)` 清洗列名 |
| High | `/index` 冷启动时 pipeline=None，跳过创建 | `api.py` | 去掉 `if pipeline is not None` 判断，始终创建 |
| High | `plot_chart` figure 泄漏（savefig 异常时不关闭） | `tools.py` | `try/finally` 确保 `plt.close(fig)` |
| High | Embedder/Generator 全局 client 无锁 | `embedder.py` + `generator.py` | 添加 `threading.Lock` 双重检查锁 |

### 确认安全（审查有误）

| 问题 | 说明 |
|------|------|
| Dockerfile CMD 引用已删除文件 | `scripts/start.sh` 存在，审查有误 |
| Docker Compose 端口映射错 | start.sh 用 `--port 8000`，映射 `8501:8000` 正确 |

**测试：** 215 个全过

---

## RAGv3 用户端 Web 前端准备（2026-06-01）

**目标：** 在 RAGv3 中构建自定义 Web 前端，替代 Chainlit，实现文件选择器 + 聊天界面。

**RAGv3 清理：**
- 删除 `rag/user_gui.py`（Streamlit 用户端，被前端替代）
- 删除 `.streamlit/`（Streamlit 配置）
- 删除 `__pycache__/`（生成文件）

**后端同步（RAG → RAGv3，10 个文件）：**
- `rag/api.py` — session_id、文件格式检查、KnowledgeBaseManager 集成
- `rag/pipeline.py` — 可选 file_path、session_id 透传
- `rag/tools.py` — SQL 注入防护、除零防护、行数限制、列名清洗
- `rag/memory.py` — TOCTOU 竞态修复
- `rag/retriever.py` — BM25 空 chunks 防护
- `rag/embedder.py` — 线程安全单例
- `rag/generator.py` — 线程安全单例 + None 返回值处理
- `rag/chunker.py` — 从 settings 读取配置
- `requirements.txt` — 版本锁定

**新增 API 端点（RAGv3）：**
- `GET /files` — 列出 `data/upload/` 目录下的文件（名称、大小、扩展名）
- `POST /index-all` — 索引 `data/upload/` 下全部文件

**前端计划：**
- 自定义 HTML/CSS/JS 聊天界面
- 水平滚动文件选择器（从 `/files` API 获取）
- 调用 `/query` API 进行问答
- 来源引用展示
- 用 `/frontend-design` skill 设计 UI

**当前状态：** 后端已就绪，前端待设计。

---

## RAGv3 自定义 Web 前端实现（2026-06-01）

**目标：** 用 HTML/CSS/JS 替代 Chainlit，实现暗黑科技风聊天界面 + 文件选择器。

**新增文件：**
- `static/index.html` — 自定义前端（~700 行）

**修改文件：**
- `rag/api.py` — 新增 `/files`、`/index-all`、`/data/*`（图片）、自动索引
- `rag/pipeline.py` — session_id 空值 fallback 为 `"default"`

**前端设计：**
- 风格：暗黑科技风（深色背景、JetBrains Mono 字体、霓虹 cyan 点缀、扫描线纹理）
- 布局：顶部水平滚动文件选择器 + 下方聊天区域
- 功能：文件卡片选择、聊天问答、来源引用、图表内联显示、点击放大

**API 端点：**
- `GET /` — 前端页面（FastAPI 直接 serve HTML）
- `GET /files` — 列出 `data/upload/` 文件（名称、大小、扩展名、图标）
- `POST /index-all` — 索引全部文件
- `GET /data/*` — serve 图表图片
- 启动时自动索引 `data/upload/`（`@app.on_event("startup")`）

**踩坑记录：**
1. **session_id 为 None** — `RAGPipeline(kb_id="rag_docs")` 创建时 `session_id=None`，查询时报 SQLite NOT NULL 错误。修复：`sid = session_id or self.session_id or "default"`
2. **图片显示两次** — `formatContent` 中 markdown 语法 `![alt](path)` 和裸路径 `data/chart_xxx.png` 被分别匹配，同一图片出现两次。修复：用 `Set` 去重
3. **图片标签被转义** — 先注入 `<img>` 再 HTML 转义，标签变成纯文本。修复：用占位符机制（先提取→转义→还原）
4. **"图表已保存为"文字多余** — 前端自动删除该文字，只保留图片

**相比 Chainlit/Streamlit 的优势：**
- 一个命令启动（`uvicorn rag.api:app`），不需要额外前端服务
- 同源 API，无跨域问题
- 完全自定义样式，不受框架限制
- 图表直接内联显示，不会裂图

**测试：** 215 个后端测试全过，前端手动测试通过

---

## RAGv3 功能增强：多用户系统（2026-06-01）

**目标：** 将 RAGv3 从单用户无状态系统升级为多用户有状态系统。

**实现过程（8 个 Task，Subagent-Driven）：**

| Task | 内容 | 测试 |
|------|------|------|
| 1 | UserDB 模块（users/conversations/chat_messages/feedback） | 11 |
| 2 | JWT 认证（hash/verify/create/decode） | 4 |
| 3 | 注册/登录 API（/register, /login, /me） | 4 |
| 4 | 对话管理 API（CRUD） | 4 |
| 5 | /query 改造（conversation_id + 消息保存）+ /feedback | 2 |
| 6 | 文件上传/删除 API（/upload, /files DELETE） | 25 |
| 7 | 前端改造（登录 + 侧边栏 + 上传 + 反馈） | 手动 |
| 8 | 全量回归 | 25 |

**新增文件：**
- `rag/user_db.py` — 用户/对话/消息/反馈 SQLite 模块
- `tests/test_user_db.py` — 11 个测试
- `tests/test_register_login.py` — 4 个测试
- `tests/test_conversations.py` — 4 个测试
- `tests/test_feedback.py` — 2 个测试

**修改文件：**
- `rag/auth.py` — 新增 JWT 认证函数
- `rag/api.py` — 新增 10+ 个 API 端点
- `static/index.html` — 登录页 + 侧边栏 + 上传/删除 + 反馈按钮
- `requirements.txt` — 新增 python-jose

**代码审查修复（3 Critical + 5 Important）：**

| 级别 | 问题 | 修复 |
|------|------|------|
| Critical | 无所有权验证（用户 A 可删用户 B 的对话） | SQL 加 user_id 条件 |
| Critical | 文件上传/删除无认证 | 加 authorization header |
| Critical | JWT 硬编码密钥 | 未设置时随机生成 + 警告 |
| Important | 重复密码哈希（user_db vs auth.py） | 统一用 auth.py 的函数 |
| Important | 前端发 session_id 而非 conversation_id | 改为发送 conversation_id |
| Important | 重复反馈无约束 | UNIQUE(message_id, user_id) |
| Important | escAttr XSS 不完整 | 完整转义 & " < > |
| Important | /query 吞掉 auth 错误 | 加日志记录 |

**测试：** 25 个全过

---

## 评估驱动修复：并发模型 + 工程质量（2026-06-01）

**来源：** 外部评估报告，发现 2 P0 + 2 P1 + 3 P2 问题

**核心问题：** "同步阻塞 + 全局锁的并发模型是阻碍多用户部署的硬伤"

### P0 修复（并发模型）

| 问题 | 文件 | 修复 |
|------|------|------|
| `/query` 同步阻塞事件循环 | `api.py` | 改为 `async def` + `await asyncio.to_thread(pipeline.query, ...)` |
| `/index-all` 同步阻塞 | `api.py` | 改为 `async def` + `await asyncio.to_thread(index_folder, ...)` |
| 全局 pipeline 锁串行化所有请求 | `concurrency.py` | ReadWriteLock 重写：yield 时释放锁，加 `_writing` 标志，读并发写互斥 |

### P1 修复（可靠性）

| 问题 | 文件 | 修复 |
|------|------|------|
| 6 处 `except Exception: pass` 静默吞错 | `api.py` | 全部改为 `logger.error()` + 错误信息 |
| ReadWriteLock 退化为普通 Lock | `concurrency.py` | yield 时释放 Condition，`read()` 加 `while _writing: wait()` |

### P2 修复（性能 + 代码质量）

| 问题 | 文件 | 修复 |
|------|------|------|
| BM25 kb_id 模式失效 | `retriever.py` | kb_id 模式从 Qdrant 加载 chunks 构建 BM25 索引 |
| `print()` 未迁移 logging | `pipeline.py` | 4 处 print 改为 logger.info |
| O(n²) 去重 | `cleaner.py` | 哈希快速路径 + 只比较最近 50 个 unique chunks |

**测试：** 25 个全过

---

## 工程基础设施优化（2026-06-01）

**来源：** 工程基础设施优化方案（docs/engineering-infra-plan.md）

**已完成：**

### pyproject.toml

- 项目元数据（name、version、requires-python）
- 依赖管理（从 requirements.txt 迁移，dev 依赖分离）
- Ruff 配置（target-version、line-length、lint rules、isort、format）
- Pytest 配置（testpaths、python_files）
- 构建系统（hatchling）

### 集中日志系统

- 新增 `rag/logging_config.py` — 集中日志配置
- `setup_logging()` — 支持 `RAG_LOG_LEVEL` / `RAG_LOG_JSON` 环境变量
- 请求 ID 中间件 — `X-Request-ID` header + `ContextVar`
- JSON 格式支持（生产环境用 `RAG_LOG_JSON=1`）
- 日志格式：`时间 | 级别 | 请求ID | 模块 | 消息`

### Ruff Lint/Format

- 安装 ruff v0.15.15
- 首次全量格式化：29 个文件
- 自动修复 66 个问题（import 排序、pyupgrade、simplify）
- 剩余 23 个非阻塞 lint 警告（可后续修）
- 创建 `.pre-commit-config.yaml`

### Embedding 缓存

- `_embed_single()` 加 `@lru_cache(maxsize=512)`
- 重复查询不重复调用 embedding API
- `@retry` 在缓存层外（失败重试，成功才缓存）

**测试：** 25 个全过

### 工程基础设施代码审查修复

| 级别 | 问题 | 修复 |
|------|------|------|
| Critical | BM25 scroll 不分页（>10k 数据丢失） | 分页循环加载 |
| Important | ContextVar 并发泄漏（线程池复用导致 request_id 串号） | `contextvars.copy_context().run` |
| Important | scroll 无读锁 | 文档标注已知限制 |
| Important | logging 初始化时机（startup 前请求丢失日志） | `setup_logging()` 移到模块级别 |

**测试：** 25 个全过

**待做：**
- Docker（RAGv3 版本）
- CI/CD（需要 GitHub）

---

## 技术债修复（2026-06-15）

**来源：** docs/tech-debt-plan.md + 计划书差距分析

**已完成（TDD，3 个提交）：**

### 1. JWT Secret 持久化

**问题：** JWT secret 每次重启随机生成，所有用户 token 立即失效。

**修复：**
- `rag/auth.py` — 新增 `_load_or_create_secret(secret_file)`
- 优先级：环境变量 `RAG_JWT_SECRET` > 文件 `data/jwt_secret.txt` > 自动生成
- 首次启动生成 secret 写入文件，后续重启读取文件
- `data/jwt_secret.txt` 已加入 `.gitignore`

**测试：** 4 个新测试（文件创建、读取已有文件、重启一致性、环境变量优先）

### 2. api.py 读写锁替换

**问题：** `api.py` 使用 `threading.Lock()`，查询和索引互斥，无法并发查询。

**修复：**
- `_pipeline_lock` 从 `threading.Lock()` 改为 `ReadWriteLock()`
- 查询端点 `/query` 使用 `read()` — 多个查询可并发
- 索引端点 `/upload`、`/delete`、`/index-all` 使用 `write()` — 独占更新

**测试：** 3 个新测试（类型检查、并发读、写阻塞读）

### 3. 注入检测增强

**问题：** `guard.py` 只有 15 个简单关键词，容易被同义词绕过。

**修复：**
- 扩充到 28 个模式
- 新增中文变体：无视、忘记设定、忽略上面
- 新增英文变体：forget、disregard、override
- 新增角色扮演检测：不受限制的AI、没有限制

**测试：** 5 个新测试（同义词、英文变体、角色扮演、绕过尝试、正常问题不误拦）

**统计：** 232 个测试全过（原 215 + 新 12 + 之前遗漏的 5）

---

## 技术债修复（第二批）（2026-06-15）

**实现方式：** 4 个子代理并行执行（2 组避免文件冲突），全部 TDD。

### 4. SQLite 统一目录

**问题：** memory.db 在项目根目录，与其他 .db 文件分散。

**修复：**
- `config.py` — 新增 `memory_db_path` 配置，默认 `data/memory.db`
- `rag/memory.py`、`rag/tracker.py`、`rag/pipeline.py` — 默认路径改为 `settings.memory_db_path`

**测试：** 3 个新测试

### 5. pipeline.py 集成 clean_document()

**问题：** 数据清洗管道（cleaner.py）从未被调用，编码检测/特殊字符清理/元数据提取全部跳过。

**修复：**
- `rag/pipeline.py` — 在 `load()` 和 `chunk()` 之间插入 `clean_document()` 调用

**测试：** 2 个新测试

### 6. generator.py 熔断降级

**问题：** 熔断时 `raise RuntimeError`，用户看到 500 错误。

**修复：**
- `rag/generator.py` — 熔断时 `return "系统繁忙，请稍后重试。"`

**测试：** 3 个新测试

### 7. BM25 SQLite 持久化

**问题：** 每次查询都从 Qdrant 全量 scroll 构建 BM25 索引，数据量大时是性能瓶颈。

**修复：**
- 新建 `rag/bm25_store.py` — `BM25Store` 类，SQLite 存储 chunks，`save_chunks`/`load_chunks`/`has_chunks`
- `rag/retriever.py` — 优先从 SQLite 加载，无数据时走 Qdrant scroll 并存入 SQLite
- `config.py` — 新增 `bm25_db_path` 配置，默认 `data/bm25_index.db`

**测试：** 8 个新测试（6 个 BM25Store + 2 个 Retriever 集成）

**统计：** 248 个测试全过（原 232 + 新 16）

---

## Phase 1：流式输出 + 追问建议 + 重新生成（2026-06-15）✅

**来源：** docs/plans/2026-06-15-phase1-streaming-plan.md（9 个 Task，Subagent-Driven）

**新增功能：**

| 功能 | 文件 | 说明 |
|------|------|------|
| 流式生成器 | `rag/generator.py` | `generate_stream()` — AsyncOpenAI 异步迭代器，逐 token yield |
| temperature 参数 | `rag/generator.py` | `generate()` 新增 `temperature` 参数，默认 0.3 |
| 公共逻辑提取 | `rag/pipeline.py` | `_prepare_context()` — guard/cache/route/retrieve/rerank/build_messages |
| 流式查询 | `rag/pipeline.py` | `query_stream()` — SSE 格式事件流 |
| 流式 API | `rag/api.py` | `POST /query/stream` — StreamingResponse + JWT 认证 |
| 追问建议 | `rag/suggest.py` | `suggest_questions()` — LLM 生成 3 个推荐追问 |
| 追问 API | `rag/api.py` | `POST /suggest` — 独立端点，异步获取 |
| 重新生成 | `rag/api.py` | `POST /regenerate` — 覆盖原消息，复用 `_prepare_context()` |
| 消息更新 | `rag/user_db.py` | `update_message()` — UPDATE 原消息内容 |

**设计决策：**
- POST + ReadableStream（非 GET + EventSource），支持 JWT + 长问题
- 追问建议独立端点（非内嵌 SSE），避免阻塞流式输出
- 重新生成用覆盖模式（非新增 + 标记），避免矛盾消息
- `_async_client` 用 `threading.Lock()`（非 `asyncio.Lock()`），避免无 event loop 报错

**测试：** 265 个全过（原 248 + 新 17）

**8 个提交：**
```
2ca5f14 feat: add temperature parameter to generate()
9b1a07b feat: add generate_stream() async generator for SSE streaming
a14030a refactor: extract _prepare_context() shared method from query()
54d53f0 feat: add suggest_questions() for follow-up suggestions
b532713 feat: add POST /regenerate with _prepare_context reuse
7481d59 feat: add query_stream() for SSE streaming
67130be fix: reset _async_client and _breaker state in conftest.py
e469427 feat: add POST /query/stream and POST /suggest endpoints
```

---

---

## Phase 2：数据能力（2026-06-15）✅

**新增模块：**

| 模块 | 文件 | 说明 |
|------|------|------|
| 反馈处理器 | `rag/feedback_processor.py` | chunk 级别权重管理（0.2~2.0），同用户去重，衰减回归 |
| 检索空白分析 | `rag/gap_analyzer.py` | 记录未解答查询，低分检测 + 关键词检测，缺口报告 |
| 文档标签 | `rag/vector_store.py` | Qdrant payload 存储 tags，检索时按标签过滤 |

**集成改动：**

| 文件 | 改动 |
|------|------|
| `rag/retriever.py` | `_rrf_fuse()` 支持 weights 参数 + tags 过滤 |
| `rag/pipeline.py` | `_prepare_context()` 获取 chunk weights，query/query_stream 记录 chunk_hashes + 触发空白分析 |
| `rag/tracker.py` | ExecutionTrace 新增 chunk_hashes 字段 |
| `rag/api.py` | QueryRequest 新增 tags，新增 /analytics/gaps、/files/{name}/tags、/tags 端点 |

**测试：** 298 个全过（原 265 + 新 33）

**5 个提交：**
```
59de68f feat: add FeedbackProcessor for chunk-level weight management
07dfb1f feat: add GapAnalyzer for retrieval gap analysis
f86c4e7 feat: add weights parameter to retriever RRF fusion
18051c0 feat: integrate feedback weights and gap analysis into pipeline
76913d0 feat: add document tagging with Qdrant payload tags
```

---

---

## Phase 5：批量导入（2026-06-15）✅

**新增模块：**

| 模块 | 文件 | 说明 |
|------|------|------|
| 批量导入器 | `rag/batch_importer.py` | CSV/Excel 解析，3 种模式：qa_pair / document / table |

**新增端点：**

| 端点 | 说明 |
|------|------|
| `POST /batch-import` | 上传 CSV/Excel，按模式解析并索引到知识库 |

**导入模式：**
- `qa_pair` — 每行一个问答对，配置 question_col + answer_col
- `document` — 每行一个文档片段，配置 content_col
- `table` — 整张表转为结构化文本（tab 分隔）

**测试：** 304 个全过（原 298 + 新 6）

---

## 下一步计划

- Phase 3：Vue 3 前端重写
- Phase 4：后端异步化 + Docker + CI/CD
- Phase 5（剩余）：数据源集成（RSS/数据库/API，可选）
