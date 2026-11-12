"""模板库路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import template_controller
from src.middlewares.rbac import require_permission
from src.middlewares.rate_limit import guard
from src.models.user import User

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", dependencies=[guard("read")])
def list_templates(
    status: str | None = None,
    source_id: int | None = None,
    search: str | None = None,
    include_noise: bool = False,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> dict:
    return template_controller.list_templates(
        db, status=status, source_id=source_id, search=search, include_noise=include_noise, limit=limit
    )


@router.get("/{template_id}", dependencies=[guard("read")])
def get_template(template_id: int, db: Session = Depends(get_db)) -> dict:
    return template_controller.get_template(db, template_id)


@router.post("/{template_id}/confirm", dependencies=[guard("write")])
def confirm(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("templates:write")),
) -> dict:
    return template_controller.confirm(db, template_id, user, request)


@router.post("/{template_id}/noise", dependencies=[guard("write")])
def mark_noise(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("templates:write")),
) -> dict:
    return template_controller.mark_noise(db, template_id, user, request)
