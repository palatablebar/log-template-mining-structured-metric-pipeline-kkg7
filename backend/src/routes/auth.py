"""认证路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import auth_controller
from src.middlewares.auth import get_current_user
from src.middlewares.rate_limit import guard
from src.models.user import User
from src.schemas.auth import LoginIn

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)) -> dict:
    return auth_controller.login(db, payload.email, payload.password, request)


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return auth_controller.me(user)


@router.get("/quota", dependencies=[guard("read")])
def quota(user: User = Depends(get_current_user)) -> dict:
    return auth_controller.quota(user)
