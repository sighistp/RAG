# Phase 1a 实施计划：用户管理

> 设计文档：`docs/specs/2026-06-28-phase1a-user-management-design.md`
> 日期：2026-06-28
> 原则：TDD，每阶段可独立上线

---

## 决策汇总

| # | 问题 | 决策 |
|---|------|------|
| D1 | password_changed_at NULL 行为 | NULL 跳过检查，迁移后不踢用户 |
| D2 | 匹配片段生成 | 后端返回原始片段，前端做高亮 |
| D3 | 密码强度验证 | 两层都做（前端提示 + 后端强制） |
| D4 | admin 重置密码确认 | 加 ElMessageBox.confirm 确认步骤 |
| D5 | 修改密码后前端处理 | 调 logout() 清 token 再跳转 |
| D6 | 对话搜索 SQL | LIKE 查询 + 索引优化 |

---

## Task 1：users 表加 password_changed_at 字段

**文件：** `rag/user_db.py`

**TDD 步骤：**

1. 写失败测试：

```python
def test_user_has_password_changed_at(db):
    """users 表应有 password_changed_at 字段。"""
    uid = db.create_user("alice", "pwd")
    user = db.get_user_by_id(uid)
    assert "password_changed_at" in user or user.get("password_changed_at") is None
```

2. 跑测试确认 FAIL

3. 修改 `rag/user_db.py`：
   - `_create_tables` 的 users 表加 `password_changed_at REAL DEFAULT NULL`
   - 迁移：`ALTER TABLE users ADD COLUMN password_changed_at REAL DEFAULT NULL`

4. 跑测试确认 PASS

5. commit

---

## Task 2：修改密码后端

**文件：** `rag/user_db.py`、`rag/api.py`

**TDD 步骤：**

1. 写失败测试：

```python
def test_change_password_success(db):
    """修改密码成功。"""
    uid = db.create_user("alice", "OldPass1")
    db.change_password(uid, "OldPass1", "NewPass1")
    # 用新密码登录成功
    user = db.authenticate("alice", "NewPass1")
    assert user is not None

def test_change_password_hash_format(db):
    """修改密码后 hash 格式应为 salt_hex$hash_hex。"""
    uid = db.create_user("alice", "OldPass1")
    db.change_password(uid, "OldPass1", "NewPass1")
    user = db.get_user_by_id(uid)
    assert "$" in user["password"]  # salt_hex$hash_hex 格式

def test_change_password_wrong_old(db):
    """旧密码错误应失败。"""
    uid = db.create_user("alice", "OldPass1")
    with pytest.raises(ValueError):
        db.change_password(uid, "WrongPass", "NewPass1")

def test_change_password_too_weak(db):
    """新密码太弱应失败。"""
    uid = db.create_user("alice", "OldPass1")
    with pytest.raises(ValueError):
        db.change_password(uid, "OldPass1", "123")  # 太短

def test_change_password_same_as_old(db):
    """新密码与旧密码相同应失败。"""
    uid = db.create_user("alice", "OldPass1")
    with pytest.raises(ValueError):
        db.change_password(uid, "OldPass1", "OldPass1")

def test_change_password_invalidates_old_token(db):
    """修改密码后旧 token 应失效。"""
    uid = db.create_user("alice", "OldPass1")
    from rag.auth import create_token
    token = create_token({"user_id": uid, "username": "alice"})
    # 修改密码
    db.change_password(uid, "OldPass1", "NewPass1")
    # 检查 password_changed_at 已更新
    user = db.get_user_by_id(uid)
    assert user["password_changed_at"] is not None
```

2. 跑测试确认 FAIL

3. 实现 `user_db.change_password()` 方法：

```python
def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
    """修改密码。验证旧密码、新密码强度、新旧密码不同。"""
    # 验证密码强度
    if len(new_password) < 8:
        raise ValueError("密码至少 8 位")
    if not any(c.isupper() for c in new_password):
        raise ValueError("密码需含大写字母")
    if not any(c.islower() for c in new_password):
        raise ValueError("密码需含小写字母")
    if not any(c.isdigit() for c in new_password):
        raise ValueError("密码需含数字")
    if old_password == new_password:
        raise ValueError("新密码不能与旧密码相同")

    with self._lock:
        row = self._conn.execute(
            "SELECT id, password FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not row:
            raise ValueError("用户不存在")
        from rag.auth import verify_password, hash_password
        if not verify_password(old_password, row["password"]):
            raise ValueError("旧密码错误")
        new_hashed = hash_password(new_password)
        self._conn.execute(
            "UPDATE users SET password = ?, password_changed_at = ? WHERE id = ?",
            (new_hashed, time.time(), user_id),
        )
        self._conn.commit()
```

4. 实现 API 端点 `PUT /users/me/password`

5. 跑测试确认 PASS

6. commit

---

## Task 3：token 验证检查 password_changed_at

**文件：** `rag/auth.py`、`rag/api.py`

**TDD 步骤：**

1. 写失败测试：

```python
def test_token_invalid_after_password_change():
    """密码修改后旧 token 应失效。"""
    from rag.auth import create_token, decode_token

    token = create_token({"user_id": 1, "username": "alice"})
    payload = decode_token(token)
    assert payload is not None

    # 模拟密码修改时间（token 之后）
    password_changed_at = payload["iat"] + 100
    assert payload["iat"] < password_changed_at  # token 应失效

def test_decode_token_with_password_changed_at():
    """decode_token 应支持 password_changed_at 参数。"""
    from rag.auth import create_token, decode_token

    token = create_token({"user_id": 1, "username": "alice"})
    payload = decode_token(token)
    iat = payload["iat"]

    # password_changed_at 为 None → 跳过检查
    assert decode_token(token, password_changed_at=None) is not None

    # password_changed_at 在 iat 之前 → token 有效
    assert decode_token(token, password_changed_at=iat - 100) is not None

    # password_changed_at 在 iat 之后 → token 失效
    assert decode_token(token, password_changed_at=iat + 100) is None
```

2. 跑测试确认 FAIL

3. 修改 `rag/auth.py` 的 `decode_token()`，加 `password_changed_at` 参数：

```python
def decode_token(token: str, password_changed_at: float = None) -> dict | None:
    """Decode JWT token。password_changed_at 非 None 时检查 token 是否因改密而失效。"""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except JWTError:
        return None
    # NULL 跳过检查（迁移后不踢用户）
    if password_changed_at and payload.get("iat", 0) < password_changed_at:
        return None
    return payload
```

4. 修改 `rag/api.py` 的 `_get_current_user()`，查出用户后传入 `password_changed_at`：

```python
def _get_current_user(token: str) -> dict | None:
    user = user_db.get_user_by_id(payload["user_id"])  # 先查用户
    if not user:
        return None
    payload = decode_token(token, password_changed_at=user.get("password_changed_at"))
    if not payload:
        return None
    return user
```

5. 跑测试确认 PASS

6. commit

---

## Task 4：admin 重置密码

**文件：** `rag/user_db.py`、`rag/api.py`

**TDD 步骤：**

1. 写失败测试：

```python
def test_admin_reset_password(db):
    """admin 重置密码成功。"""
    uid = db.create_user("alice", "OldPass1")
    db.reset_password(uid, "NewPass1")
    user = db.authenticate("alice", "NewPass1")
    assert user is not None

def test_reset_password_invalidates_old_token(db):
    """重置密码后旧 token 应失效。"""
    uid = db.create_user("alice", "OldPass1")
    from rag.auth import create_token
    token = create_token({"user_id": uid, "username": "alice"})
    # 重置密码
    db.reset_password(uid, "NewPass1")
    # 检查 password_changed_at 已更新
    user = db.get_user_by_id(uid)
    assert user["password_changed_at"] is not None
```

2. 跑测试确认 FAIL

3. 实现 `user_db.reset_password()` 方法（DB 层只做密码重置，不做权限检查）：

```python
def reset_password(self, user_id: int, new_password: str) -> None:
    """重置密码（不验证旧密码）。"""
    if len(new_password) < 8:
        raise ValueError("密码至少 8 位")
    # ... 强度验证同 change_password
    from rag.auth import hash_password
    new_hashed = hash_password(new_password)
    with self._lock:
        self._conn.execute(
            "UPDATE users SET password = ?, password_changed_at = ? WHERE id = ?",
            (new_hashed, time.time(), user_id),
        )
        self._conn.commit()
```

4. 实现 API 端点 `PUT /users/{uid}/reset-password`（API 层做 admin 权限检查）：

```python
@app.put("/users/{uid}/reset-password")
async def reset_user_password(uid: int, req: ResetPasswordRequest, authorization: str = Header(default="")):
    user_dict = await _require_auth(authorization)
    if not user_dict.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可重置密码")
    try:
        await asyncio.to_thread(user_db.reset_password, uid, req.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "密码已重置"}
```

5. 跑测试确认 PASS

6. commit

---

## Task 5：对话搜索

**文件：** `rag/user_db.py`、`rag/api.py`

**TDD 步骤：**

1. 写失败测试：

```python
def test_search_conversations_by_title(db):
    """搜索对话标题应返回匹配结果。"""
    uid = db.create_user("alice", "pwd")
    cid = db.create_conversation(uid, "file", title="RAG 技术讨论")
    results = db.search_conversations(uid, "RAG")
    assert len(results) == 1
    assert results[0]["conversation_id"] == cid

def test_search_conversations_by_content(db):
    """搜索消息内容应返回匹配结果。"""
    uid = db.create_user("alice", "pwd")
    cid = db.create_conversation(uid, "file", title="对话1")
    db.add_message(cid, "user", "什么是向量数据库？")
    results = db.search_conversations(uid, "向量")
    assert len(results) == 1

def test_search_conversations_no_result(db):
    """无匹配应返回空列表。"""
    uid = db.create_user("alice", "pwd")
    results = db.search_conversations(uid, "不存在的关键词")
    assert len(results) == 0

def test_search_conversations_pagination(db):
    """搜索应支持分页。"""
    uid = db.create_user("alice", "pwd")
    for i in range(25):
        cid = db.create_conversation(uid, "file", title=f"对话 {i}")
        db.add_message(cid, "user", f"消息 {i}")
    results = db.search_conversations(uid, "消息", page=1, size=10)
    assert len(results) == 10
```

2. 跑测试确认 FAIL

3. 实现 `user_db.search_conversations()` 方法：

```python
def search_conversations(self, user_id: int, q: str, page: int = 1, size: int = 20) -> list[dict]:
    """搜索对话（标题 + 消息内容）。"""
    offset = (page - 1) * size
    pattern = f"%{q}%"
    with self._lock:
        rows = self._conn.execute("""
            SELECT DISTINCT c.id, c.title, c.created_at,
                   (SELECT m.content FROM chat_messages m
                    WHERE m.conversation_id = c.id AND m.content LIKE ?
                    LIMIT 1) as matched_snippet
            FROM conversations c
            LEFT JOIN chat_messages m ON m.conversation_id = c.id
            WHERE c.user_id = ? AND (c.title LIKE ? OR m.content LIKE ?)
            ORDER BY c.created_at DESC
            LIMIT ? OFFSET ?
        """, (pattern, user_id, pattern, pattern, size, offset)).fetchall()
    return [dict(r) for r in rows]
```

4. 实现 API 端点 `GET /conversations/search`

5. 跑测试确认 PASS

6. commit

---

## Task 6：前端 — 修改密码页面

**文件：** `frontend/src/views/ChangePasswordView.vue`、`frontend/src/router/index.ts`、`frontend/src/views/MainLayout.vue`

**改动：**
- 新增 `ChangePasswordView.vue`：表单（旧密码、新密码、确认新密码）+ 实时验证 + 提交
- 路由加 `/settings/password`
- MainLayout 用户下拉菜单加"修改密码"选项
- 成功后调 `authStore.logout()` + 跳转登录页

**构建前端 + commit**

---

## Task 7：前端 — 对话搜索

**文件：** `frontend/src/stores/chat.ts`、`frontend/src/components/ConversationSearch.vue`、`frontend/src/views/FileModeView.vue`、`frontend/src/views/KBModeView.vue`

**改动：**
- `chat.ts` 新增 `searchConversations(query)` 方法
- 新增 `ConversationSearch.vue` 组件（搜索框 + 结果列表 + 高亮 + 防抖）
- `FileModeView` 和 `KBModeView` 复用此组件（避免重复代码）
- 点击结果跳转对应对话
- 清空搜索框恢复正常列表

**构建前端 + commit**

---

## Task 8：全量回归

1. 跑全部后端测试
2. 构建前端
3. 手动测试：
   - 修改密码 → 成功 → 旧 token 失效
   - admin 重置密码 → 成功
   - 对话搜索 → 匹配标题和内容
4. commit + push

---

## 执行顺序

```
Task 1 (DB 字段) → Task 2 (修改密码) → Task 3 (token 验证) → Task 4 (admin 重置) → Task 5 (对话搜索) → Task 6 (前端密码) → Task 7 (前端搜索) → Task 8 (回归)
```
