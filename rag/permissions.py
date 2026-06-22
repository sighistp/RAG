"""文档权限校验工具函数。

统一的权限校验入口，供 API 层和 pipeline 层调用。
不是中间件 — 各接口按需调用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from rag.user_db import UserDB


def check_doc_permission(
    db: UserDB,
    doc_name: str,
    kb_id: str,
    user: dict,
    action: str = "view",
) -> dict | None:
    """校验用户对指定文档的操作权限。

    Args:
        db: UserDB 实例
        doc_name: 文档名
        kb_id: 知识库 ID
        user: 当前用户 dict，需含 id / is_admin / permission_level
        action: "view" | "edit" | "delete"

    Returns:
        document_permission 记录 dict（有记录时）
        None（无权限记录 — 旧文档视为公开，放行）

    Raises:
        HTTPException 403: 无权操作
    """
    doc = db.get_document_permission(doc_name, kb_id)

    # 无权限记录 = 旧文档，视为公开，放行
    if not doc:
        return None

    # 管理员绕过
    if user.get("is_admin"):
        return doc

    if action == "view":
        if doc["owner_id"] == user["id"]:
            return doc
        if db.is_document_shared(doc["id"], user["id"]):
            return doc
        if user.get("permission_level", 1) >= doc["permission_level"]:
            return doc
        raise HTTPException(status_code=403, detail="无权查看该文档")

    if action in ("edit", "delete"):
        if doc["owner_id"] == user["id"]:
            return doc
        raise HTTPException(status_code=403, detail="仅文档上传者或管理员可操作")

    raise HTTPException(status_code=400, detail=f"未知操作: {action}")


def get_accessible_doc_names(db: UserDB, kb_id: str, user: dict) -> list[str]:
    """返回用户在指定知识库中有权查看的文档名列表。

    用于 RAG 检索后过滤。
    """
    if user.get("is_admin"):
        return None  # None 表示不过滤

    return db.get_accessible_doc_names(
        kb_id=kb_id,
        user_id=user["id"],
        user_level=user.get("permission_level", 1),
    )


def filter_chunks_by_permission(
    db: UserDB,
    kb_id: str,
    chunks: list,
    user: dict,
) -> list:
    """过滤掉用户无权查看的文档的 chunks。

    策略：
    - 管理员：不过滤
    - 旧文档无权限记录：视为公开，保留
    - 有权限记录的文档：按权限规则过滤

    Args:
        db: UserDB 实例
        kb_id: 知识库 ID
        chunks: Chunk 列表
        user: 当前用户 dict

    Returns:
        过滤后的 Chunk 列表
    """
    if user.get("is_admin"):
        return list(chunks)

    # 批量查询：一次性查出所有 doc_name 的权限记录（避免 N+1）
    doc_names = list(set(c.doc_name for c in chunks))
    perm_map = db.get_document_permissions_by_names(doc_names, kb_id)

    # 查出用户有权查看的文档名
    allowed_names = db.get_accessible_doc_names(
        kb_id=kb_id,
        user_id=user["id"],
        user_level=user.get("permission_level", 1),
    )
    allowed_set = set(allowed_names)

    result = []
    for c in chunks:
        perm = perm_map.get(c.doc_name)
        if perm is None:
            # 无权限记录 = 旧文档，视为公开
            result.append(c)
        elif c.doc_name in allowed_set:
            # 有权限记录且用户有权查看
            result.append(c)
        # else: 有权限记录但用户无权，过滤掉

    return result
