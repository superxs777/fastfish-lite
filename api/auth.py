"""
fastfish-lite API 鉴权。

仅支持 api_key，无 local_activation。
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import get_settings

logger = logging.getLogger(__name__)

_security = HTTPBearer(auto_error=False)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _get_api_key_from_header(request: Request) -> str | None:
    return request.headers.get("X-API-Key")


def _verify_token(token: str) -> bool:
    if not token or not token.strip():
        return False
    settings = get_settings()
    api_key = getattr(settings, "api_key", None)
    if api_key and token == api_key:
        return True
    return False


async def require_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_security)] = None,
) -> None:
    settings = get_settings()
    client_ip = _get_client_ip(request)

    if settings.allow_local_no_auth and client_ip in ("127.0.0.1", "localhost", "::1"):
        return

    token: str | None = None
    if credentials:
        token = credentials.credentials
    else:
        token = _get_api_key_from_header(request)
    if not token:
        token = request.query_params.get("api_key")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证凭证，请提供 X-API-Key 或 ?api_key=xxx",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not _verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败，API Key 无效",
            headers={"WWW-Authenticate": "Bearer"},
        )


__all__ = ["require_auth"]
