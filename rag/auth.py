"""API Key 鉴权模块"""

import hashlib
import hmac
import json
import os
import secrets
from datetime import UTC, datetime

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from jose import JWTError, jwt

from config import settings

# ---------------------------------------------------------------------------
# JWT Configuration
# ---------------------------------------------------------------------------
_JWT_SECRET: str = os.environ.get("RAG_JWT_SECRET", "")
if not _JWT_SECRET:
    import warnings

    warnings.warn(
        "RAG_JWT_SECRET 未设置，使用随机密钥（重启后 token 失效）。生产环境请设置 RAG_JWT_SECRET 环境变量。",
        stacklevel=2,
    )
    _JWT_SECRET = secrets.token_hex(32)
_JWT_ALGORITHM: str = "HS256"


# ---------------------------------------------------------------------------
# Password hashing (pbkdf2_hmac with random salt)
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash *password* with a random 16-byte salt using PBKDF2-HMAC-SHA256.

    Returns ``salt_hex$hash_hex``.
    """
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations=260_000)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Return True if *password* matches the ``salt$hash`` in *stored*."""
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
    except (ValueError, AttributeError):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations=260_000)
    return hmac.compare_digest(dk.hex(), hash_hex)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def create_token(payload: dict, expires_seconds: int = 86400) -> str:
    """Create a JWT token with *payload* and a default 24-hour expiry."""
    to_encode = payload.copy()
    to_encode["exp"] = datetime.now(UTC).timestamp() + expires_seconds
    to_encode.setdefault("iat", datetime.now(UTC).timestamp())
    return jwt.encode(to_encode, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode a JWT token. Returns the payload dict, or *None* if invalid/expired."""
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except JWTError:
        return None


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """校验 API Key，返回 user_id。auth_enabled=False 时跳过校验。"""
    if not settings.auth_enabled:
        return "anonymous"
    if api_key is None:
        raise HTTPException(status_code=401, detail="缺少 API Key，请在请求头中添加 X-API-Key")
    try:
        keys = json.loads(settings.auth_keys)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="鉴权配置格式错误")
    for user_id, key in keys.items():
        if hmac.compare_digest(api_key, key):
            return user_id
    raise HTTPException(status_code=403, detail="API Key 无效")
