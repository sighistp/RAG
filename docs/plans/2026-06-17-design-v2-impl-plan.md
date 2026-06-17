# Design v2 实现计划（修正版）

> **日期：** 2026-06-17
> **范围：** 基于 docs/specs/2026-06-17-design-v2.md

---

## 阶段 0：数据库迁移 + 后端基础（0.5 天）

### Task 0.1: conversations.mode 字段
- user_db.py: ALTER TABLE conversations ADD COLUMN mode TEXT DEFAULT 'file'
- 回填 NULL mode → 'file'
- 测试：创建对话时 mode 正确存储

### Task 0.2: analysis_cards.summary 字段
- user_db.py: ALTER TABLE analysis_cards ADD COLUMN summary TEXT DEFAULT ''
- 测试：创建卡片后 summary 默认为空

### Task 0.3: kb_metadata 表（已存在，确认）
- 确认 kb_metadata 表已有 name, description, overview 字段
- 如缺少 toc 字段，添加

### Task 0.4: kb_documents 表（已存在，确认）
- 确认 kb_documents 表已有 chunk_count, status 字段

### Task 0.5: POST /conversations 支持 mode 参数
- api.py: CreateConversationRequest 新增 mode 字段
- user_db.py: create_conversation 支持 mode 参数
- 测试：POST /conversations {mode: "kb"} → 返回 mode="kb"

**测试目标：** +5（309 → 314）

---

## 阶段 1：默认对话自动创建（0.5 天）

### Task 1.1: 进入模块时自动创建对话
- FileModeView.vue onMounted：检查当前是否有活跃对话，没有则创建
- KBModeView.vue：选择 KB 后自动创建对话
- 防止重复创建：检查 currentConversation 是否存在

### Task 1.2: 对话标题自动更新
- sendMessage 后自动更新对话标题（前 30 字符）

**测试目标：** +3（314 → 317）

---

## 阶段 2：KB 流程优化（1 天）

### Task 2.1: KB 列表页无侧边栏
- KBModeView.vue：列表页移除侧边栏，全宽显示 KB 卡片
- KB 详情页：有侧边栏，显示该 KB 的对话历史

### Task 2.2: 选择 KB 后自动创建对话
- 用户点击「进入」→ 进入详情页 → 自动创建对话（mode='kb'）

**测试目标：** +5（317 → 322）

---

## 阶段 3：目录/概述用户触发生成（1 天）

### Task 3.1: KB 目录生成 API
- POST /knowledge-bases/{id}/toc/generate
- kb_metadata.py 的 generate_toc() 已存在，只需包装 API
- 测试：调用 API → 返回目录 JSON → 存入 kb_metadata.toc

### Task 3.2: KB 概述生成 API
- POST /knowledge-bases/{id}/overview/generate
- kb_metadata.py 的 generate_summary() 已存在
- 测试：调用 API → 返回概述 → 存入 kb_metadata.overview

### Task 3.3: 前端按钮触发
- KBDetailView.vue：[生成目录] [生成概述] 按钮
- 编辑/重新生成/删除功能

**测试目标：** +10（322 → 332）

---

## 阶段 4：分析卡片设置菜单（1 天）

### Task 4.1: 摘要生成 API
- POST /analysis/cards/{id}/summary/generate — LLM 生成摘要
- PUT /analysis/cards/{id}/summary — 更新摘要
- 测试：生成摘要 → 存入 analysis_cards.summary

### Task 4.2: 设置菜单组件
- SettingsMenu.vue：编辑名称、生成摘要、添加内容、删除摘要、删除卡片

### Task 4.3: 分析卡片集成
- AnalysisCard.vue：[⚙️] 按钮 + 摘要区域显示/编辑

**测试目标：** +8（332 → 340）

---

## 阶段 5：问题归入卡片（1 天）

### Task 5.1: LLM 建议卡片 API
```
POST /analysis/suggest-card
请求：{ "question": "服务挂了怎么恢复？", "answer": "首先检查日志..." }
响应：{ "suggested_card_id": 1, "suggested_card_name": "故障排查", "confidence": 0.85, "all_cards": [...] }
```

### Task 5.2: 添加到分析弹窗
- AddToAnalysisDialog.vue：LLM 建议异步加载 + 已有卡片列表 + 新建选项
- 用户不等 LLM 就能操作

### Task 5.3: MessageBubble 集成
- [📊 添加到分析] 按钮与 [👍][👎][↻] 并排

**测试目标：** +8（340 → 348）

---

## 阶段 6：分析模块增强（1 天）

### Task 6.1: 导出功能
```
GET /analysis/cards/{id}/export?format=markdown

# 故障排查

> 本组问题主要涉及系统故障的排查和恢复。

## 问题列表

1. 服务挂了怎么恢复？
   - 来源：文件模式 - 运维手册.md
   - 添加时间：2026-06-17
```

### Task 6.2: 卡片组列表侧边栏
```
┌────────────┬─────────────────────────────────────────┐
│ 卡片组      │  分析报告                [+ 新建卡片组]   │
│            │                                          │
│ 故障排查 ● │  ┌────────────────────────────────────┐ │
│ 部署相关   │  │ 📋 故障排查              [⚙️] [展开] │ │
│ 安全配置   │  │ ...                                │ │
│            │  └────────────────────────────────────┘ │
└────────────┴─────────────────────────────────────────┘
```

**测试目标：** +5（348 → 353）

---

## 阶段 7：细节打磨 + 全量回归（1 天）

- 错误处理优化
- 全量回归测试
- 文档更新

**测试目标：** +2（353 → 355）

---

## 总结

| 阶段 | 内容 | 时间 | 测试 |
|------|------|------|------|
| 0 | 数据库迁移 + 后端基础 | 0.5 天 | +5 |
| 1 | 默认对话自动创建 | 0.5 天 | +3 |
| 2 | KB 流程优化 | 1 天 | +5 |
| 3 | 目录/概述用户触发生成 | 1 天 | +10 |
| 4 | 分析卡片设置菜单 | 1 天 | +8 |
| 5 | 问题归入卡片 | 1 天 | +8 |
| 6 | 分析模块增强 | 1 天 | +5 |
| 7 | 细节打磨 + 全量回归 | 1 天 | +2 |

**总计：** 7-8 天，355+ 测试
