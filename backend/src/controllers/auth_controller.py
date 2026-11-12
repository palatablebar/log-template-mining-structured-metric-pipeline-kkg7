"""登录 / 当前用户 / 配额查询。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.messages import MSG_LOGIN_OK
from src.middlewares.auth import current_ip
from src.models.user import User
from src.services import auth_service, audit_service, quota_service


def login(db: Session, email: str, password: str, request: Request) -> dict:
    payload = auth_service.authenticate(db, email, password)
    audit_service.record(
        db,
        user=None,
        actor_email=payload["user"]["email"],
        action="auth.login",
        entity="user",
        entity_id=str(payload["user"]["id"]),
        detail={"role": payload["user"]["role"]},
        client_ip=current_ip(request),
    )
    db.commit()
    payload["message"] = MSG_LOGIN_OK
    return payload


def me(user: User) -> dict:
    return auth_service.serialize_user(user)


def quota(user: User) -> dict:
    return quota_service.peek(user.id, user.role)
