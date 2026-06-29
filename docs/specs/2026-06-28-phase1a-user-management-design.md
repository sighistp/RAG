# Phase 1a：用户管理设计文档

> 日期：2026-06-28
> 状态：设计完成
> 范围：修改密码 + admin 重置密码 + 对话搜索

---

## 一、背景

权限 v2 已完成（Phase 1-3），系统具备完整的 KB 所有权和共享机制。现在需要补充用户管理基础功能。

## 二、功能设计

### 2.1 修改密码

**后端 API：**

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

**token 失效机制：**
- `users` 表加 `password_changed_at` 字段
- 改密码时更新 `password_changed_at = datetime.now()`
- 验证 token 时检查 `token.iat < password_changed_at`，则拒绝

**前端：**
- 用户头像下拉菜单 → "修改密码"
- 跳转到 `/settings/password` 页面
- 表单：旧密码、新密码、确认新密码
- 实时验证：密码强度指示条、两次输入一致
- 成功后提示"密码已修改，请重新登录" → 跳转登录页

### 2.2 admin 重置密码

**后端 API：**

```
PUT /users/{uid}/reset-password
仅 admin 可调用
请求体：{ new_password }
直接重置密码，不需要旧密码
同时更新 password_changed_at（使旧 token 失效）
```

**前端：**
- admin 用户管理页面 → 用户列表 → "重置密码"按钮
- 弹窗输入新密码
- 成功后提示"已重置，通知用户重新登录"

### 2.3 对话搜索

**后端 API：**

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

**搜索逻辑：**
- SQL LIKE 查询（Phase 1 先用 LIKE，后续可加 FTS5）
- 搜索 conversations.title 和 chat_messages.content
- 返回匹配的对话列表，含匹配片段
- 支持分页（page + size）

**前端：**
- 对话历史区域顶部加搜索框
- 输入后防抖 300ms 触发搜索
- 结果列表显示：对话标题 + 匹配片段（关键词高亮）
- 点击结果跳转到对应对话
- 清空搜索框恢复正常列表

---

## 三、数据模型变更

### users 表新增字段

```sql
ALTER TABLE users ADD COLUMN password_changed_at REAL DEFAULT NULL;
```

- 改密码时更新为当前时间戳
- 验证 token 时检查 `token.iat < password_changed_at`

---

## 四、API 端点清单

| 端点 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/users/me/password` | PUT | 修改自己的密码 | 登录用户 |
| `/users/{uid}/reset-password` | PUT | 重置用户密码 | admin |
| `/conversations/search` | GET | 搜索对话 | 登录用户 |

---

## 五、前端页面清单

| 页面 | 路由 | 说明 |
|------|------|------|
| 修改密码页 | `/settings/password` | 表单：旧密码、新密码、确认新密码 |
| 对话搜索 | 内嵌在对话历史区域 | 搜索框 + 结果列表 |

---

## 六、测试计划

| 测试项 | 预期 |
|--------|------|
| 修改密码：旧密码正确 | 200 |
| 修改密码：旧密码错误 | 400 |
| 修改密码：新密码太弱 | 400 |
| 修改密码：新密码与旧密码相同 | 400 |
| 修改密码：成功后旧 token 失效 | 401 |
| admin 重置密码 | 200 |
| admin 重置密码：非 admin | 403 |
| 对话搜索：匹配标题 | 返回结果 |
| 对话搜索：匹配内容 | 返回结果 |
| 对话搜索：无结果 | 空列表 |
| 对话搜索：分页 | 正确分页 |

---

## 七、依赖关系

- 修改密码依赖权限 v2 的 `password_changed_at` 字段（新增）
- 对话搜索无外部依赖
- admin 重置密码依赖 admin 角色（已有）

---

## 八、设计审查补充（2026-06-28）

### 8.1 password_changed_at NULL 行为

**决策：NULL 跳过检查（写法 A）。**

```python
# 验证 token 时：
if password_changed_at and token.iat < password_changed_at:
    raise HTTPException(401, detail="密码已修改，请重新登录")
```

**理由：** 迁移后现有用户 token 不受影响，无需重新登录。只有主动改过密码的用户才受保护。

### 8.2 对话搜索 SQL 查询优化

**决策：加索引。**

```sql
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON chat_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
```

**理由：** LEFT JOIN + LIKE 全表扫描，对话多时慢。索引可加速 JOIN 和 WHERE 过滤。

### 8.3 匹配片段生成

**决策：后端返回原始片段，前端做高亮。**

- 后端：返回匹配消息的前 100 字符（原始文本，无 HTML）
- 前端：用正则替换关键词为 `<mark>` 标签

**理由：** 后端不需要处理 HTML 转义，职责清晰。

### 8.4 密码强度验证

**决策：两层都做。**

- 前端：实时提示密码强度（用户体验）
- 后端：强制验证（安全兜底，防绕过前端直接调 API）

**验证规则：** 8+ 位，含大写字母、小写字母、数字。

### 8.5 admin 重置密码确认

**决策：加确认步骤。**

流程：点击"重置密码" → `ElMessageBox.confirm("确定要重置用户 X 的密码吗？")` → 输入新密码 → 提交。

**理由：** 防止 admin 手滑误操作。

### 8.6 修改密码后前端处理

**决策：必须调 `logout()` 清 token。**

```typescript
// 修改密码成功后
authStore.logout()  // 清除 localStorage token + Pinia user
ElMessage.success('密码已修改，请重新登录')
router.push('/login')
```

**理由：** 不能只是跳转，必须清 token，否则旧 token 仍有效。

---

## 九、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 对话搜索性能 | 数据量大时慢 | Phase 1 先用 LIKE + 索引，后续加 FTS5 |
| 密码强度验证 | 用户可能觉得太严格 | 提供密码强度指示条 |
| admin 重置密码滥用 | 安全风险 | 记录操作日志（Phase 4） |
| password_changed_at 迁移 | 现有用户受影响 | NULL 跳过检查，不踢用户 |
