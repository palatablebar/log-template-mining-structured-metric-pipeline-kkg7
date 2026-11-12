"""审计日志写入：关键动作成功后由 controller 显式调用（拿得到 entity_id）。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.models.audit_log import AuditLog
from src.models.user import User


def record(
    db: Session,
    *,
    user: User | None,
    action: str,
    entity: str = "",
    entity_id: str = "",
    detail: dict[str, Any] | None = None,
    client_ip: str = "",
    actor_email: str = "",
) -> AuditLog:
    entry = AuditLog(
        user_id=user.id if user else None,
        actor_email=(user.email if user else actor_email),
        action=action,
        entity=entity,
        entity_id=str(entity_id),
        detail=detail or {},
        client_ip=client_ip or "",
    )
    db.add(entry)
    db.flush()
    return entry
