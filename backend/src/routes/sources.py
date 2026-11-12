"""日志源与解析规则路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import source_controller
from src.middlewares.rbac import require_permission
from src.middlewares.rate_limit import guard
from src.models.user import User
from src.schemas.source import RuleIn, RulePatch, SourceIn, SourcePatch

router = APIRouter(tags=["sources"])


@router.get("/sources", dependencies=[guard("read")])
def list_sources(db: Session = Depends(get_db)) -> dict:
    return source_controller.list_sources(db)


@router.post("/sources", dependencies=[guard("write")])
def create_source(
    payload: SourceIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sources:write")),
) -> dict:
    return source_controller.create_source(db, payload.model_dump(), user, request)


@router.patch("/sources/{source_id}", dependencies=[guard("write")])
def update_source(
    source_id: int,
    payload: SourcePatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sources:write")),
) -> dict:
    return source_controller.update_source(db, source_id, payload.model_dump(exclude_none=True), user, request)


@router.get("/parse-rules", dependencies=[guard("read")])
def list_rules(source_id: int | None = None, db: Session = Depends(get_db)) -> dict:
    return source_controller.list_rules(db, source_id)


@router.post("/sources/{source_id}/parse-rules", dependencies=[guard("write")])
def create_rule(
    source_id: int,
    payload: RuleIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("parse_rules:write")),
) -> dict:
    return source_controller.create_rule(db, source_id, payload.model_dump(), user, request)


@router.patch("/parse-rules/{rule_id}", dependencies=[guard("write")])
def update_rule(
    rule_id: int,
    payload: RulePatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("parse_rules:write")),
) -> dict:
    return source_controller.update_rule(db, rule_id, payload.model_dump(exclude_none=True), user, request)
