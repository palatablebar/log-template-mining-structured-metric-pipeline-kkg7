"""模板库查询 / 确认 / 噪声标记。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.messages import MSG_TEMPLATE_CONFIRMED, MSG_TEMPLATE_IGNORED
from src.middlewares.auth import current_ip
from src.models.user import User
from src.services import audit_service, template_service


def list_templates(
    db: Session,
    *,
    status: str | None = None,
    source_id: int | None = None,
    search: str | None = None,
    include_noise: bool = False,
    limit: int = 200,
) -> dict:
    items = template_service.list_templates(
        db, status=status, source_id=source_id, search=search, include_noise=include_noise, limit=limit
    )
    return {"items": items, "total": len(items)}


def get_template(db: Session, template_id: int) -> dict:
    return template_service.get_template(db, template_id)


def confirm(db: Session, template_id: int, user: User, request: Request) -> dict:
    payload = template_service.confirm_template(db, template_id, user.email)
    audit_service.record(
        db,
        user=user,
        action="templates.confirm",
        entity="log_template",
        entity_id=str(template_id),
        detail={"status": payload["status"]},
        client_ip=current_ip(request),
    )
    db.commit()
    return {"id": template_id, "status": payload["status"], "message": MSG_TEMPLATE_CONFIRMED}


def mark_noise(db: Session, template_id: int, user: User, request: Request) -> dict:
    payload = template_service.mark_noise(db, template_id, user.email)
    audit_service.record(
        db,
        user=user,
        action="templates.mark_noise",
        entity="log_template",
        entity_id=str(template_id),
        detail={"status": payload["status"]},
        client_ip=current_ip(request),
    )
    db.commit()
    return {"id": template_id, "status": payload["status"], "message": MSG_TEMPLATE_IGNORED}
