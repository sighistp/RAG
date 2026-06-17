# Design v2 实现计划

> **日期：** 2026-06-17
> **范围：** 基于 docs/specs/2026-06-17-design-v2.md 的完整实现

---

## 阶段 0：数据库迁移（0.5 天）

### Task 0.1: conversations.mode 字段

**文件：** rag/user_db.py

- [ ] 在 _create_tables 中添加 mode 字段迁移（已有，确认正确）
- [ ] 添加迁移回填：NULL mode → 'file'
- [ ] 测试：创建对话时 mode 字段正确存储

### Task 0.2: analysis_cards.summary 字段

**文件：** rag/user_db.py

- [ ] 在 _create_tables 中添加 summary 字段迁移
- [ ] 测试：创建卡片后 summary 默认为空字符串

**提交：** `git commit -m "feat: database migration - conversations.mode + analysis_cards.summary"`

---

## 阶段 1：默认对话自动创建（0.5 天）

### Task 1.1: 进入模块时自动创建对话

**文件：** frontend/src/views/FileModeView.vue, KBModeView.vue

- [ ] FileModeView onMounted：调用 `chatStore.createConversation('file')`，如果当前没有活跃对话
- [ ] KBModeView：选择 KB 后调用 `chatStore.createConversation('kb')`
- [ ] 测试：进入文件模块 → 自动创建对话 → 侧边栏显示 → 切换页面后对话还在

### Task 1.2: 对话标题自动更新

**文件：** frontend/src/stores/chat.ts

- [ ] sendMessage 后自动更新对话标题（取前 30 个字符）
- [ ] 测试：发送消息后侧边栏标题更新

**提交：** `git commit -m "feat: auto-create conversation on module entry"`

---

## 阶段 2：KB 流程优化（1 天）

### Task 2.1: KB 列表页无侧边栏

**文件：** frontend/src/views/KBModeView.vue

- [ ] KB 列表页：移除侧边栏，右侧全宽显示 KB 卡片网格
- [ ] KB 详情页：有侧边栏，显示该 KB 的对话历史
- [ ] 路由：`/kb` → 列表页，`/kb/:id` → 详情页

### Task 2.2: 选择 KB 后自动创建对话

**文件：** frontend/src/views/KBModeView.vue

- [ ] 用户点击 KB 卡片「进入」→ 进入详情页
- [ ] 详情页 onMounted：自动创建对话（mode='kb'）
- [ ] 测试：选择 KB → 自动创建对话 → 对话关联到该 KB

**提交：** `git commit -m "feat: KB list page full-width, auto-create conversation on KB select"`

---

## 阶段 3：目录/概述用户触发生成（1 天）

### Task 3.1: KB 目录生成 API

**文件：** rag/api.py, rag/kb_metadata.py

- [ ] POST /knowledge-bases/{id}/toc/generate — LLM 生成目录
- [ ] 测试：调用 API → 返回目录 JSON → 存入 kb_metadata.toc

### Task 3.2: KB 概述生成 API

**文件：** rag/api.py

- [ ] POST /knowledge-bases/{id}/overview/generate — LLM 生成概述
- [ ] 测试：调用 API → 返回概述文本 → 存入 kb_metadata.overview

### Task 3.3: 前端按钮触发

**文件：** frontend/src/views/KBDetailView.vue

- [ ] 「生成目录」按钮 → 调用 API → 显示目录
- [ ] 「生成概述」按钮 → 调用 API → 显示概述
- [ ] 编辑/重新生成/删除功能
- [ ] 测试：点击按钮 → LLM 生成 → 显示 → 编辑 → 保存

**提交：** `git commit -m "feat: user-triggered TOC and overview generation for KB"`

---

## 阶段 4：分析卡片设置菜单（1 天）

### Task 4.1: 摘要生成 API

**文件：** rag/api.py, rag/user_db.py

- [ ] POST /analysis/cards/{id}/summary/generate — LLM 生成摘要
- [ ] PUT /analysis/cards/{id}/summary — 更新摘要
- [ ] 测试：生成摘要 → 存入 analysis_cards.summary

### Task 4.2: 设置菜单组件

**文件：** frontend/src/components/SettingsMenu.vue

- [ ] 下拉菜单：编辑名称、生成摘要、添加内容、删除摘要、删除卡片
- [ ] 每个菜单项触发对应操作

### Task 4.3: 分析卡片集成设置菜单

**文件：** frontend/src/components/AnalysisCard.vue

- [ ] 卡片标题旁显示 [⚙️] 按钮
- [ ] 点击弹出设置菜单
- [ ] 摘要区域显示/隐藏/编辑
- [ ] 测试：点击菜单 → 操作生效

**提交：** `git commit -m "feat: analysis card settings menu with summary generation"`

---

## 阶段 5：问题归入卡片（1 天）

### Task 5.1: LLM 建议卡片 API

**文件：** rag/api.py

- [ ] POST /analysis/suggest-card — LLM 分析问题主题，建议放入哪个卡片
- [ ] 返回：`{suggested_card_id, suggested_card_name, confidence}`
- [ ] 测试：发送问题 → LLM 分析 → 返回建议

### Task 5.2: 添加到分析弹窗组件

**文件：** frontend/src/components/AddToAnalysisDialog.vue

- [ ] 弹窗结构：
  - LLM 建议区域（异步加载，显示"加载中..."）
  - 已有卡片列表（单选）
  - 新建卡片组选项
  - 取消/确认按钮
- [ ] LLM 建议加载完后自动高亮推荐项
- [ ] 用户可以直接选择，不等 LLM

### Task 5.3: 消息操作按钮集成

**文件：** frontend/src/components/MessageBubble.vue

- [ ] [📊 添加到分析] 按钮与 [👍][👎][↻] 并排
- [ ] 点击弹出 AddToAnalysisDialog
- [ ] 确认后调用 API 保存问题到卡片

**提交：** `git commit -m "feat: add-to-analysis dialog with LLM suggestion"`

---

## 阶段 6：分析模块增强（1 天）

### Task 6.1: 导出功能

**文件：** rag/api.py, frontend/src/views/AnalysisModeView.vue

- [ ] GET /analysis/cards/{id}/export?format=markdown — 导出为 Markdown
- [ ] 前端：每个卡片添加「导出」按钮
- [ ] 测试：导出 → 下载 Markdown 文件

### Task 6.2: 卡片组列表侧边栏

**文件：** frontend/src/views/AnalysisModeView.vue

- [ ] 左侧侧边栏显示卡片组列表
- [ ] 点击卡片组名称 → 右侧滚动到对应卡片
- [ ] 测试：点击侧边栏 → 页面滚动到对应卡片

**提交：** `git commit -m "feat: analysis export and card group sidebar"`

---

## 阶段 7：细节打磨 + 全量回归（1 天）

### Task 7.1: 错误处理

- [ ] LLM 生成失败时的错误提示
- [ ] 网络错误时的重试机制
- [ ] 空状态提示优化

### Task 7.2: 全量回归测试

- [ ] 后端测试：python -m pytest tests/ -q
- [ ] 前端测试：cd frontend && npx vitest run
- [ ] 构建：cd frontend && npm run build
- [ ] 手动测试全流程

### Task 7.3: 文档更新

- [ ] 更新 dev-log.md
- [ ] 更新 README.md（如有需要）

**提交：** `git commit -m "chore: polish and full regression"`

---

## 总时间表

| 阶段 | 内容 | 时间 |
|------|------|------|
| 0 | 数据库迁移 | 0.5 天 |
| 1 | 默认对话自动创建 | 0.5 天 |
| 2 | KB 流程优化 | 1 天 |
| 3 | 目录/概述用户触发生成 | 1 天 |
| 4 | 分析卡片设置菜单 | 1 天 |
| 5 | 问题归入卡片 | 1 天 |
| 6 | 分析模块增强 | 1 天 |
| 7 | 细节打磨 + 全量回归 | 1 天 |

**总计：约 7-8 天**
