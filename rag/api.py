import asyncio
import contextvars
import logging
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, Security, UploadFile
from fastapi.responses import FileResponse, JSONResponse
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


class QueryResponse(BaseModel):
    answer: str = Field(..., description="回答内容")
    sources: list[dict] = Field(default=[], description="引用来源")


class FeedbackRequest(BaseModel):
    message_id: int
    value: str = Field(pattern="^(positive|negative)$")
    comment: str = None


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


@app.get("/me", summary="获取当前用户信息")
def get_me(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user = _get_current_user(token)
    return {"id": user["id"], "username": user["username"]}


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
    if not user_db.delete_conversation(cid, user["id"]):
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"status": "deleted"}


@app.get("/conversations/{cid}/messages", summary="获取对话消息")
def get_conversation_messages(cid: int, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user = _get_current_user(token)
    return user_db.get_messages(cid, user["id"])


@app.post("/feedback", summary="提交反馈")
def submit_feedback(req: FeedbackRequest, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user = _get_current_user(token)
    value_int = 1 if req.value == "positive" else -1
    user_db.add_feedback(req.message_id, user["id"], value_int, req.comment or "")
    return {"status": "ok"}


@app.get("/files", summary="列出可索引文件", description="列出 data/upload/ 目录下的所有支持格式文件")
def list_files():
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
    return {"files": files, "count": len(files)}


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
async def upload_file(file: UploadFile = File(..., description="要上传的文件"), authorization: str = Header(...)):
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
def delete_file(filename: str, authorization: str = Header(...)):
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
            user = _get_current_user(token)
        except HTTPException:
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
    )

    # Save messages to chat_messages if user and conversation_id are provided
    if user and req.conversation_id is not None:
        user_db.add_message(req.conversation_id, "user", req.question)
        user_db.add_message(req.conversation_id, "assistant", result.answer)

    return QueryResponse(answer=result.answer, sources=result.sources)


class CreateKBRequest(BaseModel):
    name: str = Field(..., description="知识库名称")


class KBResponse(BaseModel):
    kb_id: str
    name: str
    doc_count: int


@app.get("/knowledge-bases", summary="列出知识库", description="获取所有知识库列表")
def list_knowledge_bases(user_id: str = Security(verify_api_key)):
    manager = KnowledgeBaseManager()
    kbs = manager.list_kbs()
    return [KBResponse(kb_id=kb.kb_id, name=kb.name, doc_count=kb.doc_count) for kb in kbs]


@app.post("/knowledge-bases", summary="创建知识库", description="创建一个新的知识库")
def create_knowledge_base(req: CreateKBRequest, user_id: str = Security(verify_api_key)):
    manager = KnowledgeBaseManager()
    kb_id = manager.create_kb(req.name)
    return {"kb_id": kb_id, "name": req.name}


@app.delete("/knowledge-bases/{kb_id}", summary="删除知识库", description="删除指定知识库及其所有文档")
def delete_knowledge_base(kb_id: str, user_id: str = Security(verify_api_key)):
    manager = KnowledgeBaseManager()
    try:
        manager.delete_kb(kb_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=404, detail=f"知识库 {kb_id} 不存在")
    return {"status": "deleted", "kb_id": kb_id}


@app.post("/knowledge-bases/{kb_id}/documents", summary="添加文档到知识库", description="上传文档到指定知识库")
async def add_document_to_kb(kb_id: str, file: UploadFile = File(...), user_id: str = Security(verify_api_key)):
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"文件大小超过 {MAX_FILE_SIZE // 1024 // 1024} MB 限制")
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
    return {"status": "added", "kb_id": kb_id, "chunks": count}


@app.delete("/knowledge-bases/{kb_id}/documents/{doc_name}", summary="删除文档", description="从知识库中删除指定文档")
def remove_document_from_kb(kb_id: str, doc_name: str, user_id: str = Security(verify_api_key)):
    manager = KnowledgeBaseManager()
    try:
        manager.remove_document(kb_id, doc_name)
    except Exception:
        raise HTTPException(status_code=404, detail=f"文档 {doc_name} 不存在")
    return {"status": "removed", "kb_id": kb_id, "doc_name": doc_name}


class QueryKBRequest(BaseModel):
    question: str = Field(..., description="用户提问")
    top_k: int = Field(default=5, ge=1, description="返回相关文档数量")


@app.post("/knowledge-bases/{kb_id}/query", summary="查询知识库", description="对指定知识库进行语义检索")
def query_knowledge_base(kb_id: str, req: QueryKBRequest, user_id: str = Security(verify_api_key)):
    manager = KnowledgeBaseManager()
    try:
        chunks = manager.search(kb_id, req.question, top_k=req.top_k)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    results = [{"doc_name": c.doc_name, "chunk_index": c.chunk_index, "text": c.text} for c in chunks]
    return {"kb_id": kb_id, "results": results}


# ── 静态文件 & 前端 ────────────────────────────────────────────────
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
DATA_DIR_PATH = Path(__file__).resolve().parent.parent / "data"


@app.get("/", summary="前端页面", description="返回知识库助手 Web 前端")
def serve_frontend():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index, media_type="text/html")
    return JSONResponse(status_code=404, content={"error": "前端文件不存在"})


# Serve chart images from data/ directory
if DATA_DIR_PATH.is_dir():
    app.mount("/data", StaticFiles(directory=str(DATA_DIR_PATH)), name="data")

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
