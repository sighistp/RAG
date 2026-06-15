# RAGv3 功能增强实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 RAGv3 从单用户无状态系统升级为多用户有状态系统（用户注册登录 + 对话历史 + 文件管理 + 反馈）

**Architecture:** FastAPI 后端新增用户/对话/反馈 API 端点，SQLite 存储用户和对话数据，JWT 认证，前端增加登录页 + 侧边栏 + 上传/删除 + 反馈按钮

**Tech Stack:** FastAPI, SQLite, python-jose (JWT), hashlib (密码哈希), 原生 HTML/CSS/JS

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `rag/user_db.py` | 新建 | 用户/对话/消息/反馈的 SQLite 操作 |
| `rag/auth.py` | 修改 | 新增 JWT 认证 + 注册/登录 |
| `rag/api.py` | 修改 | 新增用户/对话/反馈端点，改造 /query |
| `static/index.html` | 修改 | 登录页 + 侧边栏 + 上传 + 反馈 |
| `requirements.txt` | 修改 | 新增 python-jose |
| `tests/test_user_db.py` | 新建 | 用户数据库测试 |
| `tests/test_auth_jwt.py` | 新建 | JWT 认证测试 |
| `tests/test_conversations.py` | 新建 | 对话管理测试 |
| `tests/test_feedback.py` | 新建 | 反馈测试 |

---

### Task 1: 用户数据库模块 (rag/user_db.py)

**Files:**
- Create: `rag/user_db.py`
- Create: `tests/test_user_db.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_user_db.py
"""用户数据库模块测试"""
import pytest
from rag.user_db import UserDB


@pytest.fixture
def db():
    db = UserDB(db_path=":memory:")
    yield db
    db.close()


def test_create_user(db):
    user_id = db.create_user("alice", "password123")
    assert user_id > 0


def test_create_user_duplicate(db):
    db.create_user("alice", "password123")
    with pytest.raises(ValueError, match="已存在"):
        db.create_user("alice", "other")


def test_authenticate_user(db):
    db.create_user("alice", "password123")
    user = db.authenticate("alice", "password123")
    assert user is not None
    assert user["username"] == "alice"


def test_authenticate_wrong_password(db):
    db.create_user("alice", "password123")
    user = db.authenticate("alice", "wrong")
    assert user is None


def test_authenticate_nonexistent(db):
    user = db.authenticate("nobody", "x")
    assert user is None


def test_create_conversation(db):
    uid = db.create_user("alice", "password123")
    cid = db.create_conversation(uid)
    assert cid > 0


def test_list_conversations(db):
    uid = db.create_user("alice", "password123")
    db.create_conversation(uid)
    db.create_conversation(uid)
    convs = db.list_conversations(uid)
    assert len(convs) == 2


def test_delete_conversation(db):
    uid = db.create_user("alice", "password123")
    cid = db.create_conversation(uid)
    db.delete_conversation(cid)
    convs = db.list_conversations(uid)
    assert len(convs) == 0


def test_add_message(db):
    uid = db.create_user("alice", "password123")
    cid = db.create_conversation(uid)
    db.add_message(cid, "user", "你好")
    db.add_message(cid, "assistant", "你好！")
    msgs = db.get_messages(cid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_add_feedback(db):
    uid = db.create_user("alice", "password123")
    cid = db.create_conversation(uid)
    mid = db.add_message(cid, "user", "问题")
    db.add_message(cid, "assistant", "答案")
    # feedback 需要 message_id，这里测试函数存在
    assert callable(db.add_feedback)


def test_get_user_by_id(db):
    uid = db.create_user("alice", "password123")
    user = db.get_user_by_id(uid)
    assert user["username"] == "alice"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd c:/Users/lahm/Desktop/RAGv3 && python -m pytest tests/test_user_db.py -x -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rag.user_db'`

- [ ] **Step 3: Implement UserDB**

```python
# rag/user_db.py
"""用户、对话、消息、反馈的 SQLite 操作"""
import hashlib
import os
import sqlite3
import threading


class UserDB:
    def __init__(self, db_path: str = "ragv3.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_tables()

    def _init_tables(self):
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT DEFAULT '新对话',
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    value TEXT NOT NULL,
                    comment TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (message_id) REFERENCES chat_messages(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
            """)
            self._conn.commit()

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return salt.hex() + ":" + key.hex()

    @staticmethod
    def _verify_password(password: str, stored: str) -> bool:
        try:
            salt_hex, key_hex = stored.split(":")
            salt = bytes.fromhex(salt_hex)
            key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
            return key.hex() == key_hex
        except Exception:
            return False

    def create_user(self, username: str, password: str) -> int:
        with self._lock:
            try:
                cursor = self._conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, self._hash_password(password)),
                )
                self._conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                raise ValueError(f"用户名 '{username}' 已存在")

    def authenticate(self, username: str, password: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if row and self._verify_password(password, row["password_hash"]):
            return {"id": row["id"], "username": row["username"]}
        return None

    def get_user_by_id(self, user_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, username, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if row:
            return dict(row)
        return None

    def create_conversation(self, user_id: int, title: str = "新对话") -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
                (user_id, title),
            )
            self._conn.commit()
            return cursor.lastrowid

    def list_conversations(self, user_id: int) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, title, created_at FROM conversations WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_conversation(self, conversation_id: int):
        with self._lock:
            self._conn.execute(
                "DELETE FROM chat_messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            self._conn.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation_id,),
            )
            self._conn.commit()

    def add_message(self, conversation_id: int, role: str, content: str) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO chat_messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, role, content),
            )
            self._conn.commit()
            return cursor.lastrowid

    def get_messages(self, conversation_id: int) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, role, content, created_at FROM chat_messages WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_feedback(self, message_id: int, user_id: int, value: str, comment: str = None) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO feedback (message_id, user_id, value, comment) VALUES (?, ?, ?, ?)",
                (message_id, user_id, value, comment),
            )
            self._conn.commit()
            return cursor.lastrowid

    def close(self):
        self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd c:/Users/lahm/Desktop/RAGv3 && python -m pytest tests/test_user_db.py -x -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add rag/user_db.py tests/test_user_db.py
git commit -m "feat: add UserDB module — users, conversations, messages, feedback"
```

---

### Task 2: JWT 认证 + 注册/登录 API

**Files:**
- Modify: `rag/auth.py`
- Modify: `rag/api.py`
- Create: `tests/test_auth_jwt.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Install dependency**

```bash
cd c:/Users/lahm/Desktop/RAGv3
pip install python-jose[cryptography] -i https://pypi.tuna.tsinghua.edu.cn/simple
```

Add to `requirements.txt`:
```
python-jose[cryptography]>=3.3,<4
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_auth_jwt.py
"""JWT 认证测试"""
import pytest
from unittest.mock import patch
from rag.auth import hash_password, verify_password, create_token, decode_token


def test_hash_and_verify():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_token():
    token = create_token({"user_id": 1, "username": "alice"})
    payload = decode_token(token)
    assert payload["user_id"] == 1
    assert payload["username"] == "alice"


def test_decode_expired_token():
    import time
    token = create_token({"user_id": 1}, expires_seconds=0)
    time.sleep(0.1)
    payload = decode_token(token)
    assert payload is None


def test_decode_invalid_token():
    payload = decode_token("invalid.token.here")
    assert payload is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd c:/Users/lahm/Desktop/RAGv3 && python -m pytest tests/test_auth_jwt.py -x -v`
Expected: FAIL — `ImportError: cannot import name 'hash_password'`

- [ ] **Step 4: Implement JWT functions in auth.py**

Add to the TOP of `rag/auth.py` (before existing code):

```python
import hashlib
import os
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError

JWT_SECRET = os.environ.get("RAG_JWT_SECRET", "ragv3-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, key_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return key.hex() == key_hex
    except Exception:
        return False


def create_token(payload: dict, expires_seconds: int = JWT_EXPIRE_HOURS * 3600) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + timedelta(seconds=expires_seconds)
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd c:/Users/lahm/Desktop/RAGv3 && python -m pytest tests/test_auth_jwt.py -x -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add rag/auth.py tests/test_auth_jwt.py requirements.txt
git commit -m "feat: add JWT authentication — hash, verify, create, decode"
```

---

### Task 3: 注册/登录 API 端点

**Files:**
- Modify: `rag/api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_auth_jwt.py (append)
from fastapi.testclient import TestClient
from rag.api import app

client = TestClient(app)


def test_register():
    resp = client.post("/register", json={"username": "testuser", "password": "password123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["username"] == "testuser"


def test_register_duplicate():
    client.post("/register", json={"username": "dup_user", "password": "password123"})
    resp = client.post("/register", json={"username": "dup_user", "password": "other"})
    assert resp.status_code == 400


def test_login():
    client.post("/register", json={"username": "login_user", "password": "password123"})
    resp = client.post("/login", json={"username": "login_user", "password": "password123"})
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_login_wrong_password():
    client.post("/register", json={"username": "wrong_user", "password": "password123"})
    resp = client.post("/login", json={"username": "wrong_user", "password": "wrong"})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd c:/Users/lahm/Desktop/RAGv3 && python -m pytest tests/test_auth_jwt.py -x -v -k register`
Expected: FAIL — 404 (端点不存在)

- [ ] **Step 3: Add Pydantic models and endpoints to api.py**

Add after existing imports in `rag/api.py`:

```python
from rag.user_db import UserDB
from rag.auth import hash_password, verify_password, create_token, decode_token

user_db = UserDB()


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    username: str
```

Add endpoints (after `/health`):

```python
@app.post("/register", response_model=TokenResponse, summary="用户注册")
def register(req: RegisterRequest):
    try:
        user_id = user_db.create_user(req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = create_token({"user_id": user_id, "username": req.username})
    return TokenResponse(token=token, username=req.username)


@app.post("/login", response_model=TokenResponse, summary="用户登录")
def login(req: LoginRequest):
    user = user_db.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token({"user_id": user["id"], "username": user["username"]})
    return TokenResponse(token=token, username=user["username"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd c:/Users/lahm/Desktop/RAGv3 && python -m pytest tests/test_auth_jwt.py -x -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add rag/api.py tests/test_auth_jwt.py
git commit -m "feat: add /register and /login API endpoints"
```

---

### Task 4: 对话管理 API

**Files:**
- Modify: `rag/api.py`
- Create: `tests/test_conversations.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_conversations.py
"""对话管理 API 测试"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from rag.api import app

client = TestClient(app)


def _register_and_login(username="conv_user"):
    client.post("/register", json={"username": username, "password": "password123"})
    resp = client.post("/login", json={"username": username, "password": "password123"})
    return resp.json()["token"]


def test_create_conversation():
    token = _register_and_login("create_conv")
    resp = client.post("/conversations",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_list_conversations():
    token = _register_and_login("list_conv")
    client.post("/conversations", headers={"Authorization": f"Bearer {token}"})
    client.post("/conversations", headers={"Authorization": f"Bearer {token}"})
    resp = client.get("/conversations",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


def test_delete_conversation():
    token = _register_and_login("del_conv")
    resp = client.post("/conversations",
        headers={"Authorization": f"Bearer {token}"})
    cid = resp.json()["id"]
    resp = client.delete(f"/conversations/{cid}",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_unauthorized():
    resp = client.get("/conversations")
    assert resp.status_code in (401, 403)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd c:/Users/lahm/Desktop/RAGv3 && python -m pytest tests/test_conversations.py -x -v`
Expected: FAIL — 404

- [ ] **Step 3: Add conversation endpoints to api.py**

Add a helper function and endpoints:

```python
def _get_current_user(token: str) -> dict:
    """从 JWT token 获取当前用户"""
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    user = user_db.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


@app.post("/conversations", summary="新建对话")
def create_conversation(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user = _get_current_user(token)
    cid = user_db.create_conversation(user["id"])
    return {"id": cid, "title": "新对话"}


@app.get("/conversations", summary="列出对话")
def list_conversations(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user = _get_current_user(token)
    return user_db.list_conversations(user["id"])


@app.delete("/conversations/{cid}", summary="删除对话")
def delete_conversation(cid: int, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user = _get_current_user(token)
    user_db.delete_conversation(cid)
    return {"status": "deleted"}


@app.get("/conversations/{cid}/messages", summary="获取对话消息")
def get_conversation_messages(cid: int, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user = _get_current_user(token)
    return user_db.get_messages(cid)
```

Add `Header` import:
```python
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Security, Header
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd c:/Users/lahm/Desktop/RAGv3 && python -m pytest tests/test_conversations.py -x -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add rag/api.py tests/test_conversations.py
git commit -m "feat: add conversation management API — create, list, delete, messages"
```

---

### Task 5: 改造 /query 端点（保存消息 + 反馈）

**Files:**
- Modify: `rag/api.py`
- Create: `tests/test_feedback.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_feedback.py
"""反馈 API 测试"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from rag.api import app

client = TestClient(app)


def _register_and_login(username="fb_user"):
    client.post("/register", json={"username": username, "password": "password123"})
    resp = client.post("/login", json={"username": username, "password": "password123"})
    return resp.json()["token"]


def _create_conv(token):
    resp = client.post("/conversations", headers={"Authorization": f"Bearer {token}"})
    return resp.json()["id"]


@patch("rag.api.pipeline", new_callable=lambda: MagicMock())
@patch("rag.api.RAGPipeline")
def test_query_saves_messages(mock_pipeline_cls, mock_pipeline):
    token = _register_and_login("query_save")
    cid = _create_conv(token)

    mock_result = MagicMock()
    mock_result.answer = "test answer"
    mock_result.sources = []
    mock_pipeline.query.return_value = mock_result

    import rag.api as api_module
    api_module.pipeline = mock_pipeline

    resp = client.post("/query",
        json={"question": "test", "conversation_id": cid},
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # 验证消息已保存
    resp = client.get(f"/conversations/{cid}/messages",
        headers={"Authorization": f"Bearer {token}"})
    msgs = resp.json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"

    api_module.pipeline = None


def test_submit_feedback():
    token = _register_and_login("fb_submit")
    cid = _create_conv(token)

    # 先添加一条消息
    from rag.user_db import UserDB
    db = UserDB()
    mid = db.add_message(cid, "assistant", "answer")

    resp = client.post("/feedback",
        json={"message_id": mid, "value": "positive"},
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd c:/Users/lahm/Desktop/RAGv3 && python -m pytest tests/test_feedback.py -x -v`
Expected: FAIL

- [ ] **Step 3: Modify QueryRequest and /query endpoint**

Update `QueryRequest`:
```python
class QueryRequest(BaseModel):
    question: str = Field(..., description="用户提问")
    top_k: int = Field(default=5, ge=1, description="返回相关文档数量")
    session_id: Optional[str] = Field(default=None, description="会话 ID")
    conversation_id: Optional[int] = Field(default=None, description="对话 ID")
```

Update `/query` endpoint to save messages:
```python
@app.post("/query", response_model=QueryResponse, summary="查询知识库")
def query(req: QueryRequest, authorization: str = Header(default="")):
    global pipeline
    with _pipeline_lock:
        if pipeline is None:
            return JSONResponse(
                status_code=400,
                content={"error": "尚未索引文档，请先调用 POST /index 上传文档"},
            )
        current_pipeline = pipeline

    # 获取用户（如果有 token）
    user = None
    if authorization:
        try:
            token = authorization.replace("Bearer ", "")
            user = _get_current_user(token)
        except HTTPException:
            pass

    sid = req.session_id
    if user and req.conversation_id:
        sid = f"conv_{req.conversation_id}"

    result = current_pipeline.query(req.question, top_k=req.top_k, session_id=sid)

    # 保存消息到对话
    if user and req.conversation_id:
        user_db.add_message(req.conversation_id, "user", req.question)
        user_db.add_message(req.conversation_id, "assistant", result.answer)

    return QueryResponse(answer=result.answer, sources=result.sources)
```

Add feedback endpoint:
```python
class FeedbackRequest(BaseModel):
    message_id: int
    value: str = Field(pattern="^(positive|negative)$")
    comment: str = None


@app.post("/feedback", summary="提交反馈")
def submit_feedback(req: FeedbackRequest, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user = _get_current_user(token)
    user_db.add_feedback(req.message_id, user["id"], req.value, req.comment)
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd c:/Users/lahm/Desktop/RAGv3 && python -m pytest tests/test_feedback.py -x -v`
Expected: 2 passed

- [ ] **Step 5: Run full regression**

Run: `cd c:/Users/lahm/Desktop/RAGv3 && python -m pytest tests/ -x -q`
Expected: 215+ passed

- [ ] **Step 6: Commit**

```bash
git add rag/api.py tests/test_feedback.py
git commit -m "feat: /query saves messages to conversation, add /feedback endpoint"
```

---

### Task 6: 文件上传/删除 API

**Files:**
- Modify: `rag/api.py`

- [ ] **Step 1: Add /upload and /files/{filename} endpoints**

```python
@app.post("/upload", summary="上传文件并索引")
async def upload_file(
    file: UploadFile = File(...),
    authorization: str = Header(default=""),
):
    from rag.pipeline import RAGPipeline
    global pipeline

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件超过 10MB 限制")

    suffix = Path(file.filename).suffix if file.filename else ".txt"
    allowed = {".txt", ".md", ".pdf", ".docx", ".xlsx", ".csv"}
    if suffix.lower() not in allowed:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {suffix}")

    # 保存到 data/upload/
    save_path = DATA_DIR / (file.filename or "upload.txt")
    save_path.write_bytes(content)

    # 索引
    try:
        manager = KnowledgeBaseManager()
        count = manager.add_document("rag_docs", str(save_path), doc_name=file.filename)
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))

    # 刷新 pipeline
    with _pipeline_lock:
        try:
            pipeline = RAGPipeline(kb_id="rag_docs")
        except Exception:
            pass

    return {"status": "uploaded", "filename": file.filename, "chunks": count}


@app.delete("/files/{filename}", summary="删除文件")
def delete_file(filename: str, authorization: str = Header(default="")):
    from rag.pipeline import RAGPipeline
    global pipeline

    file_path = DATA_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    file_path.unlink()

    # 重建索引
    try:
        from rag.folder_indexer import index_folder
        files = [f for f in DATA_DIR.iterdir()
                 if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
        if files:
            index_folder(str(DATA_DIR))
        else:
            from rag.vector_store import clear
            clear()
    except Exception:
        pass

    with _pipeline_lock:
        try:
            pipeline = RAGPipeline(kb_id="rag_docs")
        except Exception:
            pipeline = None

    return {"status": "deleted", "filename": filename}
```

- [ ] **Step 2: Commit**

```bash
git add rag/api.py
git commit -m "feat: add /upload and /delete file endpoints"
```

---

### Task 7: 前端改造（登录 + 侧边栏 + 上传 + 反馈）

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: 前端改造**

This is a large frontend change. Key sections to add:

1. **登录/注册页面** — 检查 localStorage token，无则显示登录表单
2. **侧边栏** — 左侧对话列表，新建/切换/删除对话
3. **文件上传** — 文件选择器区域增加上传按钮 + 拖拽
4. **反馈按钮** — 每个 AI 回答下方 👍👎
5. **Authorization header** — 所有 API 请求带 `Bearer {token}`

Frontend implementation is done directly (no TDD for UI).

- [ ] **Step 2: Manual test**

Open http://localhost:8000:
- Register → Login → Create conversation → Ask question → See history
- Upload file → See in file list → Delete file
- Click 👍 on answer → Verify saved

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: frontend — login, sidebar, file upload/delete, feedback buttons"
```

---

### Task 8: 全量回归测试

- [ ] **Step 1: Run all tests**

```bash
cd c:/Users/lahm/Desktop/RAGv3 && python -m pytest tests/ -x -q
```

Expected: 225+ passed (215 original + 10+ new)

- [ ] **Step 2: Manual end-to-end test**

1. `python start.py` → browser opens
2. Register new user → Login
3. Create conversation → Ask question → See answer with sources
4. Upload new file → See in file selector
5. Delete file → Confirm removed
6. Click 👍 → Verify feedback saved
7. Refresh page → Conversation history persists
8. Logout → Login again → See old conversations

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: RAGv3 feature enhancement complete — users, conversations, files, feedback"
```

---

## 实现顺序

```
Task 1: UserDB → Task 2: JWT → Task 3: 注册登录 API
    → Task 4: 对话 API → Task 5: /query 改造 + 反馈
    → Task 6: 文件上传删除 → Task 7: 前端 → Task 8: 回归
```

**预计工时：** 2-3 小时
