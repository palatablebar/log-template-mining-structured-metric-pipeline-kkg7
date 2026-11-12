"""告警路由：规则 / 触发记录 / 确认 / 静默 / 扫描 / 口径。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import alert_controller
from src.middlewares.rbac import require_permission
from src.middlewares.rate_limit import guard
from src.models.user import User
from src.schemas.alert import AckIn, AlertRuleIn, AlertRulePatch, SilenceIn

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/formula", dependencies=[guard("read")])
def formula() -> dict:
    return alert_controller.formula()


@router.get("/rules", dependencies=[guard("read")])
def list_rules(db: Session = Depends(get_db)) -> dict:
    return alert_controller.list_rules(db)


@router.post("/rules", dependencies=[guard("write")])
def create_rule(
    payload: AlertRuleIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts:write")),
) -> dict:
    return alert_controller.create_rule(db, payload.model_dump(), user, request)


@router.patch("/rules/{rule_id}", dependencies=[guard("write")])
def update_rule(
    rule_id: int,
    payload: AlertRulePatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts:write")),
) -> dict:
    return alert_controller.update_rule(db, rule_id, payload.model_dump(exclude_none=True), user, request)


@router.get("/events", dependencies=[guard("read")])
def list_alerts(status: str | None = None, limit: int = 100, db: Session = Depends(get_db)) -> dict:
    return alert_controller.list_alerts(db, status=status, limit=limit)


@router.post("/scan", dependencies=[guard("scan")])
def run_scan(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("scan:run")),
) -> dict:
    return alert_controller.run_scan(db, user, request)


@router.post("/events/{alert_id}/ack", dependencies=[guard("write")])
def acknowledge(
    alert_id: int,
    payload: AckIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts:ack")),
) -> dict:
    return alert_controller.acknowledge(db, alert_id, payload.model_dump(), user, request)


@router.post("/events/{alert_id}/silence", dependencies=[guard("write")])
def silence(
    alert_id: int,
    payload: SilenceIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts:silence")),
) -> dict:
    return alert_controller.silence(db, alert_id, payload.model_dump(), user, request)
