"""元信息路由：枚举 / 概览。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import meta_controller
from src.middlewares.rate_limit import guard

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/enums")
def enums() -> dict:
    return meta_controller.enums()


@router.get("/overview", dependencies=[guard("read")])
def overview(db: Session = Depends(get_db)) -> dict:
    return meta_controller.overview(db)
