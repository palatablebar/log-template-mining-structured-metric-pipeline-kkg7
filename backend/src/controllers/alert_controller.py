"""告警规则 / 触发记录 / 确认 / 静默 / 扫描。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.messages import MSG_ALERT_ACKED, MSG_ALERT_SILENCED, MSG_SCAN_DONE
from src.middlewares.auth import current_ip
from src.models.user import User
from src.services import alert_service, audit_service


def list_rules(db: Session) -> dict:
    items = alert_service.list_rules(db)
    return {"items": items, "total": len(items)}


def create_rule(db: Session, payload: dict, user: User, request: Request) -> dict:
    rule = alert_service.create_rule(db, payload, user.email)
    audit_service.record(
        db,
        user=user,
        action="alerts.rule_create",
        entity="alert_rule",
        entity_id=str(rule.id),
        detail={"name": rule.name, "metric": rule.metric, "template_id": rule.template_id},
        client_ip=current_ip(request),
    )
    db.commit()
    return {"id": rule.id, "message": "告警规则已创建"}


def update_rule(db: Session, rule_id: int, payload: dict, user: User, request: Request) -> dict:
    rule = alert_service.update_rule(db, rule_id, payload)
    audit_service.record(
        db,
        user=user,
        action="alerts.rule_update",
        entity="alert_rule",
        entity_id=str(rule.id),
        detail={key: str(value) for key, value in payload.items()},
        client_ip=current_ip(request),
    )
    db.commit()
    return {"id": rule.id, "enabled": bool(rule.enabled), "message": "告警规则已更新"}


def list_alerts(db: Session, *, status: str | None = None, limit: int = 100) -> dict:
    items = alert_service.list_alerts(db, status=status, limit=limit)
    return {"items": items, "total": len(items), "stats": alert_service.stats(db)}


def run_scan(db: Session, user: User, request: Request) -> dict:
    result = alert_service.run_scan(db, origin="manual", actor=user.email)
    audit_service.record(
        db,
        user=user,
        action="alerts.scan",
        entity="alert_event",
        entity_id=str(result.get("created", 0)),
        detail={"bucket": result.get("bucket"), "created": result.get("created", 0), "templates": result.get("templates_scanned")},
        client_ip=current_ip(request),
    )
    db.commit()
    result["message"] = MSG_SCAN_DONE
    return result


def acknowledge(db: Session, alert_id: int, payload: dict, user: User, request: Request) -> dict:
    item = alert_service.acknowledge(
        db,
        alert_id,
        user.email,
        note=payload.get("note", ""),
        silence_minutes=payload.get("silence_minutes"),
    )
    audit_service.record(
        db,
        user=user,
        action="alerts.acknowledge",
        entity="alert_event",
        entity_id=str(alert_id),
        detail={"status": item["status"], "note": payload.get("note", "")},
        client_ip=current_ip(request),
    )
    db.commit()
    return {"item": item, "message": MSG_ALERT_ACKED}


def silence(db: Session, alert_id: int, payload: dict, user: User, request: Request) -> dict:
    item = alert_service.silence(
        db, alert_id, user.email, minutes=payload.get("minutes", 30), note=payload.get("note", "")
    )
    audit_service.record(
        db,
        user=user,
        action="alerts.silence",
        entity="alert_event",
        entity_id=str(alert_id),
        detail={"minutes": payload.get("minutes", 30)},
        client_ip=current_ip(request),
    )
    db.commit()
    return {"item": item, "message": MSG_ALERT_SILENCED}


def formula() -> dict:
    return alert_service.formula()
