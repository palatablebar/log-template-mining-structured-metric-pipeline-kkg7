"""审计日志查询（三角色可读，用于复盘）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.audit_log import AuditLog


def list_audit(db: Session, *, limit: int = 50, action: str | None = None) -> dict:
    query = select(AuditLog).order_by(AuditLog.id.desc())
    if action:
        query = query.where(AuditLog.action == action)
    rows = db.execute(query.limit(limit)).scalars().all()
    items = [
        {
            "id": row.id,
            "actor_email": row.actor_email,
            "action": row.action,
            "entity": row.entity,
            "entity_id": row.entity_id,
            "detail": dict(row.detail or {}),
            "client_ip": row.client_ip,
            "occurred_at": row.occurred_at.isoformat(sep=" "),
        }
        for row in rows
    ]
    return {"items": items, "total": len(items)}
