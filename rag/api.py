import asyncio
import contextvars
import logging
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, Security, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rag.auth import create_token, decode_token, verify_api_key
from rag.knowledge_base import KnowledgeBaseManager
from rag.logging_config import set_request_id, setup_logging
from rag.user_db import UserDB

# Initialize logging at module level so it is active before any request arrives.
setup_logging()

logger = logging.getLogger(__name__)

from rag.concurrency import ReadWriteLock

app = FastAPI(title="RAG 知识库 API", description="基于检索增强生成的智能知识库系统")
pipeline = None
_pipeline_lock = ReadWriteLock()


@app.on_event("startup")
def auto_index_on_startup():
    """启动时自动索引 data/upload/ 下的文件。"""
    global pipeline
    if not DATA_DIR.is_dir():
        return
    files = [f for f in DATA_DIR.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
    if not files:
        return
    logger.info("自动索引 %d 个文件...", len(files))
    try:
        from rag.folder_indexer import index_folder
        from rag.pipeline import RAGPipeline

        stats = index_folder(str(DATA_DIR))
        logger.info("索引完成: %d 文件, %d 分块", stats["files"], stats["chunks"])
        with _pipeline_lock.write():
            pipeline = RAGPipeline(kb_id="rag_docs")
    except Exception as e:
        logger.warning("启动索引失败: %s", e)


@app.middleware("http")
async def request_id_middleware(request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    set_request_id(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Vue Router SPA fallback: browser requests to known frontend paths → serve index.html
_VUE_ROUTES = {"/files", "/knowledge", "/analytics"}
_VUE_ROUTE_PREFIXES = {"/knowledge/"}


@app.middleware("http")
async def spa_fallback_middleware(request, call_next):
    path = request.url.path
    accept = request.headers.get("accept", "")
    # Only for GET requests from browsers to known Vue routes
    if request.method == "GET" and "text/html" in accept:
        if path in _VUE_ROUTES or any(path.startswith(p) for p in _VUE_ROUTE_PREFIXES):
            index = STATIC_DIR / "index.html"
            if index.exists():
                return FileResponse(index, media_type="text/html")
    return await call_next(request)


# 数据目录
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "upload"
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".xlsx", ".csv"}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class QueryRequest(BaseModel):
    question: str = Field(..., description="用户提问")
    top_k: int = Field(default=5, ge=1, description="返回相关文档数量")
    session_id: str | None = Field(default=None, description="会话 ID（用于多轮对话记忆）")
    conversation_id: int | None = Field(default=None, description="对话 ID")
    doc_name: str | None = Field(default=None, description="限定检索的文档名称")
    tags: list[str] | None = Field(default=None, description="按标签过滤文档")


class QueryResponse(BaseModel):
    answer: str = Field(..., description="回答内容")
    sources: list[dict] = Field(default=[], description="引用来源")


class StreamQueryRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1)
    session_id: str | None = None
    conversation_id: int | None = None
    doc_name: str | None = None
    tags: list[str] | None = None


class SuggestRequest(BaseModel):
    question: str = Field(..., max_length=2000)
    answer: str = Field(..., max_length=5000)


class FeedbackRequest(BaseModel):
    message_id: int
    value: str = Field(pattern="^(positive|negative)$")
    comment: str = None


class RegenerateRequest(BaseModel):
    conversation_id: int
    message_id: int


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    username: str


# Module-level UserDB instance
_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "users.db"
user_db = UserDB(str(_DB_PATH))


# ── FeedbackProcessor 单例 ──────────────────────────────────────────────
_feedback_processor = None


def get_feedback_processor():
    """返回模块级 FeedbackProcessor 单例，避免每次查询都创建新实例。"""
    global _feedback_processor
    if _feedback_processor is None:
        from rag.feedback_processor import FeedbackProcessor
        _feedback_processor = FeedbackProcessor(str(_DB_PATH))
    return _feedback_processor


@app.get("/health", summary="健康检查", description="检查服务是否正常运行")
def health():
    components = {}
    try:
        from rag.vector_store import _get_client

        qdrant_client = _get_client()
        qdrant_client.get_collections()
        components["qdrant"] = "ok"
    except Exception as e:
        logger.error("Qdrant 健康检查失败: %s", e)
        components["qdrant"] = "error"

    try:
        import sqlite3

        from config import settings as _settings

        conn = sqlite3.connect(_settings.analysis_db_path)
        conn.execute("SELECT 1")
        conn.close()
        components["sqlite"] = "ok"
    except Exception as e:
        logger.error("SQLite 健康检查失败: %s", e)
        components["sqlite"] = "error"

    status = "healthy" if all(v == "ok" for v in components.values()) else "degraded"
    return {"status": status, "components": components}


@app.post("/register", response_model=TokenResponse, summary="用户注册")
async def register(req: RegisterRequest):
    try:
        user_id = await asyncio.to_thread(user_db.create_user, req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = create_token({"user_id": user_id, "username": req.username})
    return TokenResponse(token=token, username=req.username)


@app.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(req: LoginRequest):
    user = await asyncio.to_thread(user_db.authenticate, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token({"user_id": user["id"], "username": user["username"]})
    return TokenResponse(token=token, username=user["username"])


@app.get("/me", summary="获取当前用户信息")
async def get_me(user_id: str = Security(verify_api_key), authorization: str = Header(default="")):
    # When auth_enabled=True, verify_api_key already validated the token/JWT.
    # Try to resolve full user info from JWT when authorization is provided.
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user = await asyncio.to_thread(_get_current_user, token)
        if user:
            return {"id": user["id"], "username": user["username"]}
    # auth_enabled=False → user_id="anonymous"; or token didn't resolve to a user
    return {"id": user_id, "username": "anonymous"}


def _get_current_user(token: str) -> dict | None:
    """从 JWT token 获取当前用户。返回 None 表示认证失败。

    注意：此函数在 asyncio.to_thread 中调用，不能抛出 HTTPException
    （否则会被包装成 500 错误）。调用方必须检查返回值并抛出 HTTPException。
    """
    payload = decode_token(token)
    if not payload:
        return None
    user = user_db.get_user_by_id(payload["user_id"])
    if not user:
        return None
    return user


@app.post("/conversations", summary="新建对话")
async def create_conversation(authorization: str = Header(default="")):
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    token = authorization.replace("Bearer ", "")
    user = await asyncio.to_thread(_get_current_user, token)
    if not user:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    cid = await asyncio.to_thread(user_db.create_conversation, user["id"])
    return {"id": cid, "title": "新对话"}


@app.get("/conversations", summary="列出对话")
async def list_conversations(authorization: str = Header(default="")):
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    token = authorization.replace("Bearer ", "")
    user = await asyncio.to_thread(_get_current_user, token)
    if not user:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    return await asyncio.to_thread(user_db.list_conversations, user["id"])


@app.delete("/conversations/{cid}", summary="删除对话")
async def delete_conversation(cid: int, authorization: str = Header(default="")):
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    token = authorization.replace("Bearer ", "")
    user = await asyncio.to_thread(_get_current_user, token)
    if not user:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    if not await asyncio.to_thread(user_db.delete_conversation, cid, user["id"]):
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"status": "deleted"}


@app.get("/conversations/{cid}/messages", summary="获取对话消息")
async def get_conversation_messages(cid: int, authorization: str = Header(default="")):
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    token = authorization.replace("Bearer ", "")
    user = await asyncio.to_thread(_get_current_user, token)
    if not user:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    return await asyncio.to_thread(user_db.get_messages, cid, user["id"])


@app.post("/feedback", summary="提交反馈")
async def submit_feedback(req: FeedbackRequest, authorization: str = Header(default="")):
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    token = authorization.replace("Bearer ", "")
    user = await asyncio.to_thread(_get_current_user, token)
    if not user:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    value_int = 1 if req.value == "positive" else -1
    owned = await asyncio.to_thread(user_db.message_belongs_to_user, req.message_id, user["id"])
    if not owned:
        raise HTTPException(status_code=404, detail="消息不存在或无权操作")
    await asyncio.to_thread(user_db.add_feedback, req.message_id, user["id"], value_int, req.comment or "")
    return {"status": "ok"}


@app.post("/regenerate", summary="重新生成回答")
async def regenerate(req: RegenerateRequest, authorization: str = Header(default="")):
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    token = authorization.replace("Bearer ", "")
    user = await asyncio.to_thread(_get_current_user, token)
    if not user:
        raise HTTPException(status_code=401, detail="token 无效或已过期")

    messages = await asyncio.to_thread(user_db.get_messages, req.conversation_id, user["id"])
    target = None
    user_question = None
    for i, msg in enumerate(messages):
        if msg["id"] == req.message_id and msg["role"] == "assistant":
            target = msg
            if i > 0 and messages[i - 1]["role"] == "user":
                user_question = messages[i - 1]["content"]
            break

    if not target:
        raise HTTPException(status_code=404, detail="消息不存在")
    if not user_question:
        raise HTTPException(status_code=400, detail="找不到对应的用户问题")

    with _pipeline_lock.read():
        if pipeline is None:
            raise HTTPException(status_code=400, detail="尚未索引文档")
        current_pipeline = pipeline

    session_id = f"conv_{req.conversation_id}"
    prepared, error = current_pipeline._prepare_context(user_question, session_id, None)
    if error:
        raise HTTPException(status_code=400, detail=error)

    if prepared["route"] == "agent":
        new_answer = await asyncio.to_thread(current_pipeline.agent.run, user_question)
    else:
        from rag.generator import generate
        new_answer = await asyncio.to_thread(generate, prepared["messages"], 0.7)

    await asyncio.to_thread(user_db.update_message, req.message_id, new_answer, user["id"])
    return {"message_id": req.message_id, "answer": new_answer}


@app.get("/files", summary="列出可索引文件", description="列出 data/upload/ 目录下的所有支持格式文件")
async def list_files():
    files = []
    if DATA_DIR.is_dir():
        for fpath in sorted(DATA_DIR.iterdir()):
            if fpath.is_file() and fpath.suffix.lower() in SUPPORTED_EXTENSIONS:
                size = fpath.stat().st_size
                files.append(
                    {
                        "name": fpath.name,
                        "size": size,
                        "size_human": _human_size(size),
                        "ext": fpath.suffix.lower(),
                    }
                )
    # Batch check which files are in KBs
    if files:
        filenames = [f["name"] for f in files]
        in_kb_set = await asyncio.to_thread(_check_files_in_kb, filenames)
        for f in files:
            f["in_kb"] = f["name"] in in_kb_set
    return {"files": files, "count": len(files)}


def _check_files_in_kb(filenames: list[str]) -> set[str]:
    """批量检查哪些文件已编入知识库，返回已编入的文件名集合。"""
    import sqlite3
    db_path = str(_DB_PATH)
    try:
        conn = sqlite3.connect(db_path)
        placeholders = ",".join("?" * len(filenames))
        rows = conn.execute(
            f"SELECT DISTINCT filename FROM kb_documents WHERE filename IN ({placeholders}) AND status = 'indexed'",
            filenames
        ).fetchall()
        conn.close()
        return {r[0] for r in rows}
    except Exception:
        return set()


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


@app.post(
    "/upload",
    summary="上传文件",
    description="上传文件到 data/upload/ 并索引，支持 txt/md/pdf/docx/xlsx/csv 格式，最大 10MB",
)
async def upload_file(file: UploadFile = File(..., description="要上传的文件"), authorization: str = Header(default="")):
    from rag.pipeline import RAGPipeline

    global pipeline

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"文件大小超过 {MAX_FILE_SIZE // 1024 // 1024} MB 限制")

    # Sanitize filename to prevent path traversal
    filename = Path(file.filename).name if file.filename else "upload.txt"
    suffix = Path(filename).suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail=f"不支持的文件格式: {suffix}，支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Ensure DATA_DIR exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Save file to DATA_DIR
    dest = DATA_DIR / filename
    try:
        dest.write_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存文件失败: {e}")

    # Index the file
    try:
        manager = KnowledgeBaseManager()
        count = manager.add_document("rag_docs", str(dest), doc_name=filename)
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))

    # Refresh pipeline
    with _pipeline_lock.write():
        try:
            pipeline = RAGPipeline(kb_id="rag_docs")
        except Exception as e:
            logger.error("Pipeline 刷新失败（上传后）: %s", e)

    return {"status": "uploaded", "filename": filename, "chunks": count}


@app.delete("/files/{filename}", summary="删除文件", description="从 data/upload/ 删除文件并重新索引")
async def delete_file(filename: str, authorization: str = Header(default="")):
    from rag.folder_indexer import index_folder
    from rag.pipeline import RAGPipeline
    from rag.vector_store import clear as clear_collection

    global pipeline

    # Sanitize filename to prevent path traversal
    safe_name = Path(filename).name
    file_path = DATA_DIR / safe_name

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"文件 {safe_name} 不存在")

    # Delete the file
    file_path.unlink()

    # Re-index remaining files
    remaining = [f for f in DATA_DIR.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]

    with _pipeline_lock.write():
        if remaining:
            try:
                index_folder(str(DATA_DIR))
                pipeline = RAGPipeline(kb_id="rag_docs")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"重新索引失败: {e}")
        else:
            # No files left — clear the collection and reset pipeline
            try:
                clear_collection()
            except Exception as e:
                logger.error("清空集合失败: %s", e)
            pipeline = None

    return {"status": "deleted", "filename": safe_name}


@app.post("/files/{filename}/tags", summary="为文档添加标签", description="为指定文档的所有分块添加标签")
async def add_tags_to_file(filename: str, tags: list[str], authorization: str = Header(default="")):
    from qdrant_client.models import FieldCondition, Filter, MatchValue, PointIdsList, UpdateOperation
    from rag.vector_store import _get_client, COLLECTION_NAME

    safe_name = Path(filename).name
    client = _get_client()
    if not client.collection_exists(COLLECTION_NAME):
        raise HTTPException(status_code=404, detail="集合不存在")

    # Find all points for this document
    search_filter = Filter(must=[FieldCondition(key="doc_name", match=MatchValue(value=safe_name))])
    results = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=10000,
        scroll_filter=search_filter,
        with_payload=False,
    )
    points = results[0] if isinstance(results, tuple) else results
    if not points:
        raise HTTPException(status_code=404, detail=f"文档 {safe_name} 不存在")

    point_ids = [p.id for p in points]
    # Merge with existing tags
    for pid in point_ids:
        existing = client.retrieve(collection_name=COLLECTION_NAME, ids=[pid], with_payload=True)
        if existing and existing[0].payload:
            existing_tags = existing[0].payload.get("tags", [])
        else:
            existing_tags = []
        merged = list(set(existing_tags + tags))
        client.set_payload(
            collection_name=COLLECTION_NAME,
            payload={"tags": merged},
            points=[pid],
        )

    return {"status": "updated", "filename": safe_name, "tags": tags, "points_updated": len(point_ids)}


@app.get("/tags", summary="获取所有标签", description="获取当前知识库中所有已使用的标签")
async def list_tags():
    from rag.vector_store import _get_client, COLLECTION_NAME

    client = _get_client()
    if not client.collection_exists(COLLECTION_NAME):
        return {"tags": []}

    all_tags = set()
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=10000,
            offset=offset,
            with_payload=True,
        )
        for p in points:
            if p.payload and "tags" in p.payload:
                all_tags.update(p.payload["tags"])
        if offset is None:
            break

    return {"tags": sorted(all_tags)}


@app.post("/index-all", summary="索引全部文件", description="索引 data/upload/ 目录下的所有文件")
async def index_all(user_id: str = Security(verify_api_key)):
    from rag.folder_indexer import index_folder
    from rag.pipeline import RAGPipeline

    global pipeline
    if not DATA_DIR.is_dir():
        raise HTTPException(status_code=400, detail="data/upload/ 目录不存在")
    try:
        stats = await asyncio.to_thread(index_folder, str(DATA_DIR))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    with _pipeline_lock.write():
        try:
            pipeline = await asyncio.to_thread(RAGPipeline, kb_id="rag_docs")
        except Exception as e:
            logger.error("Pipeline 刷新失败（全量索引后）: %s", e)
    return {"status": "indexed", **stats}


@app.post("/index", summary="索引文档", description="上传文档并添加到知识库，支持 txt/md/pdf/docx/xlsx 格式，最大 10MB")
async def index(file: UploadFile = File(..., description="要索引的文档文件"), user_id: str = Security(verify_api_key)):
    from rag.pipeline import RAGPipeline

    global pipeline
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"文件大小超过 {MAX_FILE_SIZE // 1024 // 1024} MB 限制")
    suffix = Path(file.filename).suffix if file.filename else ".txt"
    allowed = {".txt", ".md", ".pdf", ".docx", ".xlsx", ".csv"}
    if suffix.lower() not in allowed:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {suffix}，支持: {', '.join(allowed)}")
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(content)
        tmp_path = tmp.name
    finally:
        tmp.close()
    try:
        manager = KnowledgeBaseManager()
        count = manager.add_document("rag_docs", tmp_path, doc_name=file.filename or "upload")
    except Exception as e:
        os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail=str(e))
    os.unlink(tmp_path)
    # 刷新 pipeline（冷启动时创建，运行时更新）
    with _pipeline_lock.write():
        try:
            pipeline = RAGPipeline(kb_id="rag_docs")
        except Exception as e:
            logger.error("Pipeline 刷新失败（索引后）: %s", e)
    return {"status": "indexed", "chunks": count}


@app.post("/batch-import", summary="批量导入", description="上传 Excel/CSV 批量导入到知识库")
async def batch_import(
    file: UploadFile = File(...),
    mode: str = "qa_pair",
    config: str = "{}",
    user_id: str = Security(verify_api_key),
):
    import json as _json
    from rag.batch_importer import BatchImporter

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件过大")

    suffix = Path(file.filename).suffix.lower() if file.filename else ".csv"
    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {suffix}")

    # 保存临时文件
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(content)
        tmp_path = tmp.name
    finally:
        tmp.close()

    try:
        parsed_config = _json.loads(config)
    except _json.JSONDecodeError:
        parsed_config = {}

    try:
        importer = BatchImporter()
        chunks = importer.parse(tmp_path, mode=mode, config=parsed_config)

        if not chunks:
            raise HTTPException(status_code=400, detail="解析结果为空")

        # 索引到知识库
        from rag.embedder import embed
        from rag.vector_store import add

        embeddings = embed([c.text for c in chunks])
        add(chunks, embeddings)

        # 刷新 pipeline
        global pipeline
        from rag.pipeline import RAGPipeline
        with _pipeline_lock.write():
            try:
                pipeline = RAGPipeline(kb_id="rag_docs")
            except Exception as e:
                logger.error("Pipeline 刷新失败: %s", e)

        return {"status": "imported", "chunks": len(chunks), "mode": mode}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        os.unlink(tmp_path)


@app.post("/query", response_model=QueryResponse, summary="查询知识库", description="对已索引的文档进行语义检索问答")
async def query(req: QueryRequest, user_id: str = Security(verify_api_key), authorization: str = Header(default="")):
    global pipeline
    with _pipeline_lock.read():
        if pipeline is None:
            return JSONResponse(
                status_code=400,
                content={"error": "尚未索引文档，请先调用 POST /index 上传文档"},
            )
        current_pipeline = pipeline

    # Try to resolve user from authorization header (optional)
    user = None
    if authorization:
        try:
            token = authorization.replace("Bearer ", "")
            user = await asyncio.to_thread(_get_current_user, token)
        except (HTTPException, Exception):
            logger.debug("Query auth failed (non-critical): token invalid or expired")

    # Determine session_id: use conversation-based session if user + conversation_id provided
    session_id = req.session_id
    if user and req.conversation_id is not None:
        session_id = f"conv_{req.conversation_id}"

    result = await asyncio.to_thread(
        contextvars.copy_context().run,
        current_pipeline.query,
        req.question,
        top_k=req.top_k,
        session_id=session_id,
        doc_name=req.doc_name,
        tags=req.tags,
    )

    # Save messages to chat_messages if user and conversation_id are provided
    if user and req.conversation_id is not None:
        await asyncio.to_thread(user_db.add_message, req.conversation_id, "user", req.question)
        await asyncio.to_thread(user_db.add_message, req.conversation_id, "assistant", result.answer)

    return QueryResponse(answer=result.answer, sources=result.sources)


@app.post("/query/stream", summary="流式查询知识库", description="SSE 流式返回查询结果")
async def query_stream(
    req: StreamQueryRequest,
    user_id: str = Security(verify_api_key),
    authorization: str = Header(default=""),
):
    global pipeline
    with _pipeline_lock.read():
        if pipeline is None:
            return JSONResponse(status_code=400, content={"error": "尚未索引文档"})
        current_pipeline = pipeline

    user = None
    if authorization:
        try:
            token = authorization.replace("Bearer ", "")
            user = await asyncio.to_thread(_get_current_user, token)
        except (HTTPException, Exception):
            pass

    session_id = req.session_id
    if user and req.conversation_id is not None:
        session_id = f"conv_{req.conversation_id}"

    async def event_generator():
        answer_buffer = ""
        async for event in current_pipeline.query_stream(
            req.question, top_k=req.top_k, session_id=session_id, doc_name=req.doc_name, tags=req.tags
        ):
            # 从 token 事件中提取 answer 用于持久化
            if '"type": "token"' in event:
                try:
                    import json as _json
                    data = _json.loads(event.removeprefix("data: ").strip())
                    answer_buffer += data.get("content", "")
                except Exception:
                    pass
            yield event
        # 流式完成后持久化到 chat_messages
        if user and req.conversation_id is not None and answer_buffer:
            await asyncio.to_thread(user_db.add_message, req.conversation_id, "user", req.question)
            await asyncio.to_thread(user_db.add_message, req.conversation_id, "assistant", answer_buffer)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/suggest", summary="生成追问建议", description="基于问答生成 3 个推荐追问")
async def suggest(req: SuggestRequest, user_id: str = Security(verify_api_key)):
    from rag.suggest import suggest_questions
    questions = await asyncio.to_thread(suggest_questions, req.question, req.answer)
    return {"questions": questions}


class BatchImportRequest(BaseModel):
    mode: str = Field(pattern="^(qa_pair|document|table)$")
    config: dict = Field(default_factory=dict)


class CreateKBRequest(BaseModel):
    name: str = Field(..., description="知识库名称")


class KBResponse(BaseModel):
    kb_id: str
    name: str
    doc_count: int


@app.get("/knowledge-bases", summary="列出知识库", description="获取所有知识库列表")
async def list_knowledge_bases(user_id: str = Security(verify_api_key)):
    def _list():
        manager = KnowledgeBaseManager()
        return manager.list_kbs()
    kbs = await asyncio.to_thread(_list)
    return [KBResponse(kb_id=kb.kb_id, name=kb.name, doc_count=kb.doc_count) for kb in kbs]


@app.post("/knowledge-bases", summary="创建知识库", description="创建一个新的知识库")
async def create_knowledge_base(req: CreateKBRequest, user_id: str = Security(verify_api_key)):
    def _create():
        manager = KnowledgeBaseManager()
        return manager.create_kb(req.name)
    kb_id = await asyncio.to_thread(_create)
    return {"kb_id": kb_id, "name": req.name}


@app.delete("/knowledge-bases/{kb_id}", summary="删除知识库", description="删除指定知识库及其所有文档")
async def delete_knowledge_base(kb_id: str, user_id: str = Security(verify_api_key)):
    manager = KnowledgeBaseManager()
    try:
        manager.delete_kb(kb_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")
    # Clean up SQLite metadata
    def _cleanup():
        import sqlite3
        conn = sqlite3.connect(str(_DB_PATH))
        try:
            conn.execute("DELETE FROM kb_documents WHERE kb_id = ?", (kb_id,))
            conn.execute("DELETE FROM kb_metadata WHERE kb_id = ?", (kb_id,))
            conn.commit()
        finally:
            conn.close()
    await asyncio.to_thread(_cleanup)
    return {"status": "deleted", "kb_id": kb_id}


@app.post("/knowledge-bases/{kb_id}/documents", summary="添加文档到知识库", description="上传文档到指定知识库")
async def add_document_to_kb(kb_id: str, file: UploadFile = File(...), user_id: str = Security(verify_api_key)):
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"文件大小超过 {MAX_FILE_SIZE // 1024 // 1024} MB 限制")
    filename = Path(file.filename).name if file.filename else "unnamed.txt"
    suffix = Path(file.filename).suffix if file.filename else ".txt"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(content)
        tmp_path = tmp.name
    finally:
        tmp.close()
    try:
        manager = KnowledgeBaseManager()
        count = manager.add_document(kb_id, tmp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        os.unlink(tmp_path)
    # Insert into kb_documents
    def _insert_doc():
        import sqlite3
        db_path = str(_DB_PATH)
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO kb_documents (kb_id, filename, file_path, chunk_count, status) VALUES (?, ?, ?, ?, 'indexed')",
                (kb_id, filename, None, count)
            )
            # Derive human-readable name from kb_id (format: kb_slug_hex)
            readable_name = kb_id.split("_")[1] if "_" in kb_id else kb_id
            conn.execute(
                "INSERT OR IGNORE INTO kb_metadata (kb_id, name) VALUES (?, ?)",
                (kb_id, readable_name)
            )
            conn.commit()
        finally:
            conn.close()
    await asyncio.to_thread(_insert_doc)
    return {"status": "added", "kb_id": kb_id, "chunks": count}


@app.delete("/knowledge-bases/{kb_id}/documents/{doc_name}", summary="删除文档", description="从知识库中删除指定文档")
async def remove_document_from_kb(kb_id: str, doc_name: str, user_id: str = Security(verify_api_key)):
    manager = KnowledgeBaseManager()
    try:
        manager.remove_document(kb_id, doc_name)
    except Exception:
        raise HTTPException(status_code=404, detail=f"文档 {doc_name} 不存在")
    # Clean up kb_documents record
    def _cleanup():
        import sqlite3
        conn = sqlite3.connect(str(_DB_PATH))
        try:
            conn.execute("DELETE FROM kb_documents WHERE kb_id = ? AND filename = ?", (kb_id, doc_name))
            conn.commit()
        finally:
            conn.close()
    await asyncio.to_thread(_cleanup)
    return {"status": "removed", "kb_id": kb_id, "doc_name": doc_name}


class KBOverviewRequest(BaseModel):
    overview: str


class KBTocRequest(BaseModel):
    toc: dict


class KBSummaryRequest(BaseModel):
    summary: str


class QueryKBRequest(BaseModel):
    question: str = Field(..., description="用户提问")
    top_k: int = Field(default=5, ge=1, description="返回相关文档数量")


@app.post("/knowledge-bases/{kb_id}/query", summary="查询知识库", description="对指定知识库进行语义检索")
async def query_knowledge_base(kb_id: str, req: QueryKBRequest, user_id: str = Security(verify_api_key)):
    manager = KnowledgeBaseManager()
    try:
        chunks = manager.search(kb_id, req.question, top_k=req.top_k)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    results = [{"doc_name": c.doc_name, "chunk_index": c.chunk_index, "text": c.text} for c in chunks]
    return {"kb_id": kb_id, "results": results}


@app.get("/knowledge-bases/{kb_id}", summary="获取知识库详情")
async def get_knowledge_base_detail(kb_id: str, user_id: str = Security(verify_api_key)):
    """获取知识库详情，包括元数据、文档列表、概述、目录。"""
    def _get():
        import sqlite3
        from config import settings as _settings

        manager = KnowledgeBaseManager()
        kbs = manager.list_kbs()
        kb = next((k for k in kbs if k.kb_id == kb_id), None)
        if not kb:
            return None

        # 从 SQLite 获取元数据
        db_path = str(_DB_PATH)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            meta = conn.execute("SELECT * FROM kb_metadata WHERE kb_id = ?", (kb_id,)).fetchone()
            docs = conn.execute("SELECT * FROM kb_documents WHERE kb_id = ?", (kb_id,)).fetchall()
            return {
                "kb_id": kb_id,
                "name": meta["name"] if meta else kb.name,
                "description": meta["description"] if meta else "",
                "overview": meta["overview"] if meta else "",
                "doc_count": kb.doc_count,
                "documents": [dict(d) for d in docs],
            }
        finally:
            conn.close()

    result = await asyncio.to_thread(_get)
    if not result:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return result


@app.put("/knowledge-bases/{kb_id}/overview", summary="更新知识库概述")
async def update_kb_overview(kb_id: str, req: KBOverviewRequest, user_id: str = Security(verify_api_key)):
    def _update():
        import sqlite3
        from config import settings as _settings

        db_path = str(_DB_PATH)
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO kb_metadata (kb_id, name, overview) VALUES (?, '', ?) "
                "ON CONFLICT(kb_id) DO UPDATE SET overview = ?",
                (kb_id, req.overview, req.overview)
            )
            conn.commit()
        finally:
            conn.close()

    await asyncio.to_thread(_update)
    return {"status": "updated"}


@app.put("/knowledge-bases/{kb_id}/documents/{doc_name}/toc", summary="更新文档目录")
async def update_doc_toc(kb_id: str, doc_name: str, req: KBTocRequest, user_id: str = Security(verify_api_key)):
    import json
    def _update():
        import sqlite3

        db_path = str(_DB_PATH)
        conn = sqlite3.connect(db_path)
        try:
            toc_str = json.dumps(req.toc, ensure_ascii=False)
            cur = conn.execute(
                "UPDATE kb_documents SET toc = ? WHERE kb_id = ? AND filename = ?",
                (toc_str, kb_id, doc_name)
            )
            if cur.rowcount == 0:
                return False
            conn.commit()
            return True
        finally:
            conn.close()

    result = await asyncio.to_thread(_update)
    if not result:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"status": "updated"}


@app.put("/knowledge-bases/{kb_id}/documents/{doc_name}/summary", summary="更新文档概述")
async def update_doc_summary(kb_id: str, doc_name: str, req: KBSummaryRequest, user_id: str = Security(verify_api_key)):
    def _update():
        import sqlite3

        db_path = str(_DB_PATH)
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.execute(
                "UPDATE kb_documents SET summary = ? WHERE kb_id = ? AND filename = ?",
                (req.summary, kb_id, doc_name)
            )
            if cur.rowcount == 0:
                return False
            conn.commit()
            return True
        finally:
            conn.close()

    result = await asyncio.to_thread(_update)
    if not result:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"status": "updated"}


# ── 分析端点 ──────────────────────────────────────────────────────

@app.get("/analytics/gaps/summary", summary="检索空白分析统计")
async def get_gap_summary():
    def _get():
        from rag.gap_analyzer import GapAnalyzer
        from config import settings as _settings
        ga = GapAnalyzer(_settings.memory_db_path)
        try:
            return ga.get_summary()
        finally:
            ga.close()
    return await asyncio.to_thread(_get)


@app.get("/analytics/gaps", summary="未解答问题列表")
async def get_gaps(limit: int = 50):
    def _get():
        from rag.gap_analyzer import GapAnalyzer
        from config import settings as _settings
        ga = GapAnalyzer(_settings.memory_db_path)
        try:
            return ga.get_gaps(limit=limit)
        finally:
            ga.close()
    return await asyncio.to_thread(_get)


# ── 静态文件 & 前端 ────────────────────────────────────────────────
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
DATA_DIR_PATH = Path(__file__).resolve().parent.parent / "data"


@app.get("/", summary="前端页面", description="返回知识库助手 Web 前端")
def serve_frontend():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index, media_type="text/html")
    return JSONResponse(status_code=404, content={"error": "前端文件不存在"})


# Vue Router catch-all: serve index.html for client-side routes
# Only for paths that don't conflict with API endpoints
@app.get("/chat/{path:path}", include_in_schema=False)
@app.get("/login", include_in_schema=False)
def serve_spa():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index, media_type="text/html")
    return JSONResponse(status_code=404, content={"error": "前端文件不存在"})


# Serve only safe subdirectories (NOT the entire data/ which contains .db, jwt_secret, etc.)
DATA_CHARTS_DIR = DATA_DIR_PATH / "charts"
DATA_CHARTS_DIR.mkdir(exist_ok=True)
if DATA_CHARTS_DIR.is_dir():
    app.mount("/data/charts", StaticFiles(directory=str(DATA_CHARTS_DIR)), name="data-charts")
DATA_UPLOAD_DIR = DATA_DIR_PATH / "upload"
if DATA_UPLOAD_DIR.is_dir():
    app.mount("/data/upload", StaticFiles(directory=str(DATA_UPLOAD_DIR)), name="data-upload")

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
