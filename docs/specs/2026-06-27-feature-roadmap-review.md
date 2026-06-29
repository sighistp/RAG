# RAGv3 功能路线图设计审查

> 日期：2026-06-27
> 范围：6 阶段 15 功能全面审查

---

## 一、总览

| 阶段 | 功能 | 复杂度 | 审查结论 |
|------|------|--------|---------|
| Phase 1 | 修改密码 + 对话搜索 | 低 | ✅ 可行，补 2 项 |
| Phase 2 | 文件搜索 + 文档预览 + 批量操作 | 中 | ✅ 可行，补 1 项 |
| Phase 3 | 跨 KB 搜索 + KB 导入导出 | 中 | ✅ 可行 |
| Phase 4 | 文档标签 + 定时同步 + 操作日志 | 中 | ⚠️ 定时同步需明确场景 |
| Phase 5 | KB 模板 + 自定义 Prompt + API 文档 | 中 | ✅ 可行 |
| Phase 6 | 文档版本 | 高 | ⚠️ 复杂度高，建议拆分 |

---

## 二、Phase 1：用户管理（修改密码 + 对话搜索）

### 2.1 修改密码

**后端：**

```
PUT /users/me/password
请求体：{ old_password, new_password, confirm_password }
验证：
  - 旧密码正确
  - 新密码匹配确认密码
  - 新密码强度：8+ 位，含大小写 + 数字
  - 新密码不能与旧密码相同
成功：更新 password + salt，返回 200
```

**前端：**
- 用户头像下拉菜单 → "修改密码"
- 表单：旧密码、新密码、确认新密码
- 实时验证：密码强度指示条、两次输入一致
- 成功后提示"密码已修改，请重新登录" → 跳转登录页

**审查意见：**

| # | 问题 | 建议 |
|---|------|------|
| 1 | 改密码后旧 token 仍有效 | users 表加 `password_changed_at` 字段，改密码时更新。验证 token 时检查 `token.iat < password_changed_at` 则拒绝。比 token_version 方案更简单 |
| 2 | 没有"忘记密码"功能 | 补充：admin 可重置任意用户密码（见下方补充功能） |

### 2.2 对话搜索

**后端：**

```
GET /conversations/search?q=xxx&page=1&size=20
搜索范围：conversations.title + chat_messages.content
返回：
  {
    "results": [
      {
        "conversation_id": 1,
        "title": "...",
        "matched_snippet": "...匹配片段（高亮关键词）...",
        "created_at": "..."
      }
    ],
    "total": 42,
    "page": 1
  }
```

**前端：**
- 对话历史区域顶部加搜索框
- 输入后防抖 300ms 触发搜索
- 结果列表显示：对话标题 + 匹配片段（关键词高亮）
- 点击结果跳转到对应对话
- 清空搜索框恢复正常列表

**审查意见：**

| # | 问题 | 建议 |
|---|------|------|
| 1 | 只搜 content 不够 | 搜索范围加 title 字段 |
| 2 | 缺分页 | 加 page + size 参数 |
| 3 | 搜索性能 | content 字段无索引，数据量大时慢。建议加 SQLite FTS5 全文索引（后续优化，Phase 1 先用 LIKE） |

### 2.3 补充功能：admin 重置密码

**为什么需要：** 公司内部没有邮箱验证，用户忘记密码后只能找 admin。没有这个功能，用户会卡死。

**后端：**

```
PUT /users/{uid}/reset-password
仅 admin 可调用
请求体：{ new_password }
直接重置密码，不需要旧密码
```

**前端：**
- admin 用户管理页面 → 用户列表 → "重置密码"按钮
- 弹窗输入新密码
- 成功后提示"已重置，通知用户重新登录"

### 2.4 补充功能：对话置顶

**为什么需要：** 对话多了之后，重要对话被淹没。用户需要快速找到常用对话。

**后端：**

```
conversations 表加 pinned INTEGER DEFAULT 0
PUT /conversations/{id}/pin   → pinned=1
PUT /conversations/{id}/unpin → pinned=0
GET /conversations 返回时 pinned=1 的排在最前面
```

**前端：**
- 对话列表中置顶对话有 📌 标识
- 右键/长按对话 → "置顶"/"取消置顶"

**说明：** 只做"置顶"，不做"收藏"。两个概念都是"标记重要对话"，做两个反而让用户困惑。置顶够用。

---

## 三、Phase 2：文件管理（搜索 + 预览 + 批量）

### 3.1 文件搜索

**后端：**

```
GET /files/search?q=xxx&page=1&size=20
搜索范围：文件名（SQL LIKE）
返回：
  {
    "results": [
      {
        "filename": "运维手册.pdf",
        "size_human": "2.3 MB",
        "ext": ".pdf",
        "scope": "public"
      }
    ],
    "total": 5,
    "page": 1
  }
```

**审查意见：**

| # | 问题 | 建议 |
|---|------|------|
| 1 | 文件名搜索 vs 内容搜索 | Phase 2 只做文件名搜索（SQL LIKE），内容搜索（向量检索）留给 Phase 3 的"跨 KB 搜索"。降低 Phase 2 复杂度 |
| 2 | 搜索结果加 scope/is_owner | 返回时带上权限信息，前端可直接显示标签 |

### 3.2 文档预览

**后端：**

```
GET /files/{filename}/preview
返回：文件内容的纯文本/HTML 版本
支持格式：txt/md 直接返回，pdf/docx 转文本后返回
```

**前端：**
- 文件列表点击文件名 → 弹出预览面板（右侧抽屉或新标签）
- 预览面板显示纯文本内容
- 支持搜索关键词高亮

**审查意见：**

| # | 问题 | 建议 |
|---|------|------|
| 1 | PDF/DOCX 预览 | 后端复用现有 loader.py 的 load() 函数，返回文本 |
| 2 | 预览权限 | 复用 check_doc_permission(action="view") |
| 3 | 大文件 | 限制预览前 50KB，超出部分提示"文件过大，请下载查看" |

### 3.3 批量操作

**支持操作：**
- 批量删除
- 批量移动到知识库
- 批量切换 scope（Phase 2 权限系统上线后）

**后端：**

```
POST /files/batch-delete
请求体：{ filenames: ["a.txt", "b.pdf"] }
逐个检查权限，返回成功/失败列表

POST /files/batch-move
请求体：{ filenames: ["a.txt"], kb_id: "kb_xxx" }
```

**前端：**
- 文件列表加复选框
- 选中后顶部出现操作栏："已选 N 个 [删除] [移到知识库]"
- 操作前二次确认

### 3.4 补充功能：文件重命名

**为什么需要：** 上传后名字错了，现在只能删了重传。成本低但很常用。

**后端：**

```
PUT /files/{filename}/rename
请求体：{ new_name }
验证：
  - 新文件名不重复
  - 新文件名合法（无路径遍历）
执行：
  - 重命名磁盘文件
  - 更新 document_permissions.doc_name
  - 更新 Qdrant 中所有 point 的 doc_name 元数据
  - 更新 bm25_index 中的 doc_name
```

### 3.5 导出对话

**后端：**

```
GET /conversations/{id}/export?format=markdown
返回：Markdown 格式的对话记录
  # 对话标题
  > 用户：问题
  > 助手：回答 [1] 来源文件

  ---
  **来源：**
  [1] 运维手册.md — 第3段
```

**支持格式：**
- Markdown（可读性好，适合分享）
- JSON（程序化处理，适合备份）

**前端：**
- 对话详情页 → 右上角菜单 → "导出对话"
- 选择格式后下载文件

---

## 四、Phase 3：知识库高级（跨 KB 搜索 + 导入导出）

### 4.1 跨知识库搜索

**后端：**

```
POST /search
请求体：{ question, kb_ids: ["kb_a", "kb_b"], top_k: 10 }
逻辑：
  - 对每个 kb_id 并行检索 top_k
  - 合并结果，按相关度排序
  - 返回时标注每条结果属于哪个 KB
```

**审查意见：**

| # | 问题 | 建议 |
|---|------|------|
| 1 | 性能 | 并行检索多个 KB，用 asyncio.gather |
| 2 | 权限 | 只搜索用户有权限访问的 KB（过滤 private KB） |
| 3 | 结果去重 | 不同 KB 可能有相同文档，按 doc_name + chunk_index 去重 |

### 4.2 KB 导入导出

**导出：**

```
GET /knowledge-bases/{kb_id}/export
返回：ZIP 包
  - metadata.json（KB 信息、文档列表）
  - documents/（所有原始文件）
  - permissions.json（权限配置）
```

**导入：**

```
POST /knowledge-bases/import
请求体：multipart/form-data（ZIP 文件）
逻辑：
  - 解压 ZIP
  - 创建新 KB
  - 上传所有文件到新 KB
  - 恢复权限配置（可选）
```

**审查意见：**

| # | 问题 | 建议 |
|---|------|------|
| 1 | 大 KB 导出耗时 | 异步任务 + 进度条 |
| 2 | 导入时权限 | 默认不恢复权限（新 KB 用当前用户为 owner） |
| 3 | 格式 | ZIP 包比 JSON 好，包含原始文件 |

### 4.3 补充功能：创建者显示

**为什么需要：** 多人共享时，用户需要知道这是谁的文件/KB。

**实现：**
- `GET /files` 返回加 `owner_name` 字段
- `GET /knowledge-bases` 返回加 `owner_name` 字段
- 前端列表显示"由 张三 创建"

---

## 五、Phase 4：标签与同步（标签 + 同步 + 日志）

### 5.1 文档标签

**后端：**

```
POST /files/{filename}/tags
请求体：{ tags: ["重要", "技术文档"] }

DELETE /files/{filename}/tags
请求体：{ tags: ["重要"] }

GET /files?tag=技术文档
按标签过滤文件
```

**审查意见：**

| # | 问题 | 建议 |
|---|------|------|
| 1 | 标签存哪里 | 存在 Qdrant payload 中（已有 tags 字段），不加新表 |
| 2 | 标签管理 | 需要一个"标签列表"端点，返回所有已用标签 + 文件数 |
| 3 | 标签颜色 | 前端给标签分配颜色（hash 取色），提升辨识度 |

### 5.2 定时同步

**需要明确场景：**

| 场景 | 说明 | 复杂度 |
|------|------|--------|
| A. GitHub 仓库文件同步 | 已有 `_sync_repo_files`，只需定时触发 | 低 |
| B. 外部数据源同步 | RSS/DB/API 数据源定时拉取 | 中 |
| C. 数据备份 | 定时备份 data/ 和 qdrant_data/ | 低 |

**建议：** Phase 4 只做场景 A（仓库文件定时同步），场景 B 用现有的 `data_sources/` 模块，场景 C 不需要额外代码（Docker volume 已保证数据持久化，服务器磁盘不丢就行）。

**实现：**
- APScheduler 定时任务（已在 requirements.txt 中）
- 配置：`SYNC_INTERVAL_HOURS=6`（环境变量）
- 失败重试 + 日志记录

### 5.3 操作日志

**后端：**

```
新建 audit_log 表：
  id, user_id, action, resource_type, resource_id, details, created_at

记录的操作：
  - 文件：上传/删除/切换scope/重命名
  - 知识库：创建/删除/添加文档/移除文档
  - 用户：登录/修改密码/角色变更
  - 共享：共享/取消共享

GET /audit-log?page=1&size=50&action=delete&resource_type=file
admin 可查看所有日志
普通用户只能看自己的操作
```

**审查意见：**

| # | 问题 | 建议 |
|---|------|------|
| 1 | 日志表会很大 | 定期清理（保留 90 天），或按月分表 |
| 2 | 性能 | 异步写入，不阻塞主请求 |
| 3 | 隐私 | 日志不记录具体内容，只记录操作类型和资源 ID |

---

## 六、Phase 5：模板与扩展（模板 + Prompt + API 文档）

### 6.1 KB 模板

**场景：** 新建 KB 时选择模板，自动配置结构。

**模板类型：**

| 模板 | 预设 | 适用 |
|------|------|------|
| 通用知识库 | 默认配置 | 一般用途 |
| 项目文档 | 目录结构 + 概述模板 | 项目组 |
| 课程资料 | 章节结构 + 问答模板 | 学校 |
| FAQ | 问答对结构 | 客服/IT 支持 |

**实现：**
- 模板存在 `prompts/templates/` 目录（YAML 文件）
- 创建 KB 时可选模板，自动填充 overview 和 toc 结构
- 不影响现有功能，纯前端引导

### 6.2 自定义 Prompt

**后端：**

```
PUT /settings/prompt
请求体：{ prompt_type: "system", content: "你是..." }
存储：users 表加 prompt_override 字段（JSON）
```

**审查意见：**

| # | 问题 | 建议 |
|---|------|------|
| 1 | 安全风险 | 用户自定义 prompt 可能绕过安全防护，需要 sanitize |
| 2 | 范围 | 只允许修改 system prompt 的附加部分，不能覆盖核心指令 |
| 3 | 恢复默认 | 提供"恢复默认"按钮 |

### 6.3 API 文档

**实现：**
- FastAPI 自带 Swagger UI（`/docs`）和 ReDoc（`/redoc`）
- 只需要确保所有端点有正确的 docstring 和 summary
- 可选：生成独立的 API 文档页面

**审查意见：** 成本最低，主要是补全端点文档字符串。

---

## 七、Phase 6：高级功能（文档版本）

### 7.1 文档版本控制

**设计：**

```
新增 document_versions 表：
  id, doc_name, kb_id, version, file_path, created_by, created_at

流程：
  - 上传同名文件 → 自动创建新版本（version++）
  - 旧版本文件移到 /app/data/versions/{doc_name}/v{N}/
  - 保留最近 N 个版本（默认 10）
  
API：
  GET  /files/{filename}/versions          → 版本列表
  GET  /files/{filename}/versions/{v}      → 获取指定版本内容
  POST /files/{filename}/versions/{v}/restore → 恢复到指定版本
  DELETE /files/{filename}/versions/{v}    → 删除指定版本
```

**审查意见：**

| # | 问题 | 建议 |
|---|------|------|
| 1 | 存储空间 | 限制保留版本数（默认 10），超出自动删除最旧版本 |
| 2 | 向量索引 | 恢复版本时需要重新索引 |
| 3 | 复杂度 | 这是最复杂的功能，建议最后做，且先做只保留 3 个版本的 MVP |
| 4 | 合并冲突 | 不做合并（简单覆盖），如果多人同时编辑同一文件，最后上传的赢 |

**建议拆分：**

```
Phase 6a（MVP）— 1 天：
  - 上传同名文件时弹出确认弹窗："文件已存在，是否覆盖？"
  - 覆盖前自动备份旧文件到 /app/data/backup/{filename}/
  - 最多保留最近 3 个备份
  - 无版本表、无版本 API（最小改动）

Phase 6b（完整）— 4 天：
  - 新增 document_versions 表
  - 版本列表 + 查看历史版本
  - 恢复到指定版本
  - 版本对比（diff）
  - 可配置保留版本数
  - 版本占用空间统计
```

---

## 八、补充功能清单

以下是审查过程中发现的用户大概率会要的功能，按优先级排列：

### 高优先级（建议加入 Phase 1-2）

| 功能 | 说明 | 工作量 |
|------|------|--------|
| admin 重置密码 | 用户忘记密码时唯一出路 | 0.5 天 |
| 对话置顶 | 重要对话快速访问（只做置顶，不做收藏） | 0.5 天 |
| 文件重命名 | 上传后改名，不用删了重传 | 1 天 |
| 导出对话 | 对话记录导出为 Markdown | 1 天 |
| 创建者显示 | 文件/KB 列表显示 owner_name，多人共享时辨识 | 0.5 天 |

### 中优先级（建议加入 Phase 3-4）

| 功能 | 说明 | 工作量 |
|------|------|--------|
| 用户昵称/头像 | 多人共享时辨识 | 1 天 |
| 文件夹/分组 | 文件多了需要组织 | 2 天 |
| 操作确认弹窗 | 删除前二次确认 | 0.5 天 |
| 标签管理面板 | 查看所有标签 + 文件数 | 1 天 |

### 低优先级（后续考虑）

| 功能 | 说明 | 工作量 |
|------|------|--------|
| 在线用户列表 | 知道谁在用 | 1 天 |
| 使用统计 | admin 看系统使用情况 | 2 天 |
| 批量删除对话 | 清理对话历史 | 0.5 天 |
| 多语言支持 | 中英文切换 | 3 天 |
| 暗色模式 | UI 主题切换 | 2 天 |

---

## 九、最终路线图

```
Phase 1（用户管理）— 预计 3 天
  ├── 修改密码（含 password_changed_at 失效旧 token）
  ├── admin 重置密码
  ├── 对话搜索（标题 + 内容，LIKE 查询）
  ├── 对话置顶（只做置顶，不做收藏）
  └── 创建者显示（KB 列表加 owner_name）

Phase 2（文件管理）— 预计 5 天
  ├── 文件搜索（仅文件名，SQL LIKE）
  ├── 文档预览（txt/md/pdf/docx，复用 loader.py）
  ├── 批量操作（删除 + 移动到 KB）
  ├── 文件重命名（磁盘 + permissions + Qdrant 联动）
  ├── 导出对话（Markdown/JSON 格式）
  └── 创建者显示（文件列表加 owner_name）

Phase 3（知识库高级）— 预计 5 天
  ├── 跨 KB 搜索（向量检索 + 并行 + 去重）
  ├── KB 导入导出（ZIP 格式）
  └── 用户昵称

Phase 4（标签与日志）— 预计 4 天
  ├── 文档标签（存 Qdrant payload）
  ├── 定时同步（仓库文件定时同步，不含备份）
  ├── 操作日志（audit_log 表，保留 90 天）
  └── 标签管理面板

Phase 5（模板与扩展）— 预计 3 天
  ├── KB 模板（YAML 文件，前端引导）
  ├── 自定义 Prompt（只允许附加，不覆盖核心）
  └── API 文档补全（Swagger + ReDoc）

Phase 6（高级功能）— 预计 4 天
  ├── Phase 6a（1 天）：同名文件覆盖确认 + 自动备份（最多 3 份）
  └── Phase 6b（3 天）：完整版本管理（版本表 + 列表 + 恢复 + diff）

总计：约 24 天（单人开发）
```

---

## 十、风险与依赖

| 风险 | 影响 | 应对 |
|------|------|------|
| 文档版本存储空间爆炸 | 磁盘满 | 限制版本数 + 定期清理 |
| 对话搜索性能 | 数据量大时慢 | Phase 1 先用 LIKE，后续加 FTS5 |
| 自定义 Prompt 安全 | 绕过安全防护 | 只允许附加 prompt，不覆盖核心 |
| 跨 KB 搜索延迟 | 多 KB 并行检索 | asyncio.gather + 超时控制 |
| 定时同步失败 | 数据不一致 | 失败重试 + 日志记录 + 告警 |
