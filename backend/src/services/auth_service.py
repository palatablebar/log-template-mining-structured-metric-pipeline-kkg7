"""登录与用户信息。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.models.base import now_local
from src.models.user import User
from src.utils.errors import AppError
from src.utils.jwt import create_access_token, create_refresh_token
from src.utils.password import verify_password


def authenticate(db: Session, email: str, password: str) -> dict:
    normalized = email.strip().lower()
    user = db.execute(select(User).where(User.email == normalized)).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AppError(codes.AUTH_INVALID, "邮箱或密码不正确", f"email={normalized}")
    user.last_login_at = now_local()
    db.flush()
    return {
        "access_token": create_access_token(user.id, user.role, user.email),
        "refresh_token": create_refresh_token(user.id, user.role, user.email),
        "token_type": "bearer",
        "user": serialize_user(user),
    }


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": bool(user.is_active),
        "last_login_at": user.last_login_at.isoformat(sep=" ") if user.last_login_at else None,
    }
