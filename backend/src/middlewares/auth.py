"""认证中间件：Bearer → request.state.user；健康检查与登录白名单。"""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants import error_codes as codes
from src.models.user import User
from src.utils.errors import AppError
from src.utils.jwt import decode_token

PUBLIC_PATHS = ("/health", "/api/health", "/auth/login", "/api/auth/login", "/docs", "/openapi.json", "/api/meta/enums")


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    return header.split(" ", 1)[1].strip()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_bearer(request)
    if not token:
        raise AppError(codes.AUTH_REQUIRED, "请先登录", "missing Authorization header")
    payload = decode_token(token)
    subject = payload.get("sub")
    if subject is None:
        raise AppError(codes.AUTH_INVALID, "登录状态无效，请重新登录", "missing sub")
    user = db.get(User, int(subject))
    if user is None or not user.is_active:
        raise AppError(codes.AUTH_INVALID, "登录状态无效，请重新登录", "user missing/inactive")
    request.state.user = user
    return user


def current_ip(request: Request) -> str:
    return getattr(request.state, "client_ip", "") or ""


def trace_id_of(request: Request) -> str:
    return getattr(request.state, "trace_id", "")
