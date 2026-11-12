"""导入 / 采样路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import import_controller
from src.middlewares.rbac import require_permission
from src.middlewares.rate_limit import guard
from src.models.user import User
from src.schemas.imports import ApplyIn, MineIn

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("/sample")
def sample() -> PlainTextResponse:
    """确定性样本文件（249 行 = 240 新格式 + 9 噪声），供前端「载入内置样本」与 curl 测试。"""
    return PlainTextResponse(import_controller.get_sample(), media_type="text/plain; charset=utf-8")


@router.get("/sample/meta")
def sample_meta() -> dict:
    return import_controller.sample_meta()


@router.post("/mine", dependencies=[guard("write")])
def mine(
    payload: MineIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("events:import")),
) -> dict:
    return import_controller.mine(db, payload.text, payload.apply, user, request)


@router.post("/apply", dependencies=[guard("write")])
def apply(
    payload: ApplyIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("events:import")),
) -> dict:
    return import_controller.mine(db, payload.text, True, user, request)
