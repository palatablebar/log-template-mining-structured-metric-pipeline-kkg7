"""审计日志路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import audit_controller
from src.middlewares.rbac import require_permission
from src.middlewares.rate_limit import guard
from src.models.user import User

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", dependencies=[guard("read")])
def list_audit(
    limit: int = 50,
    action: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("audit:read")),
) -> dict:
    return audit_controller.list_audit(db, limit=limit, action=action)
