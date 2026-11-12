"""日志源与解析规则。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.messages import (
    MSG_RULE_CREATED,
    MSG_RULE_UPDATED,
    MSG_SOURCE_CREATED,
    MSG_SOURCE_UPDATED,
)
from src.middlewares.auth import current_ip
from src.models.user import User
from src.services import audit_service, source_service


def list_sources(db: Session) -> dict:
    items = source_service.list_sources(db)
    return {"items": items, "total": len(items)}


def create_source(db: Session, payload: dict, user: User, request: Request) -> dict:
    source = source_service.create_source(db, payload)
    audit_service.record(
        db,
        user=user,
        action="sources.create",
        entity="log_source",
        entity_id=str(source.id),
        detail={"name": source.name, "format": source.log_format},
        client_ip=current_ip(request),
    )
    db.commit()
    return {"id": source.id, "name": source.name, "message": MSG_SOURCE_CREATED}


def update_source(db: Session, source_id: int, payload: dict, user: User, request: Request) -> dict:
    source = source_service.update_source(db, source_id, payload)
    audit_service.record(
        db,
        user=user,
        action="sources.update",
        entity="log_source",
        entity_id=str(source.id),
        detail={key: str(value) for key, value in payload.items()},
        client_ip=current_ip(request),
    )
    db.commit()
    return {"id": source.id, "collect_status": source.collect_status, "message": MSG_SOURCE_UPDATED}


def list_rules(db: Session, source_id: int | None = None) -> dict:
    items = source_service.list_rules(db, source_id)
    return {"items": items, "total": len(items)}


def create_rule(db: Session, source_id: int, payload: dict, user: User, request: Request) -> dict:
    rule = source_service.create_rule(db, source_id, payload)
    audit_service.record(
        db,
        user=user,
        action="parse_rules.create",
        entity="parse_rule",
        entity_id=str(rule.id),
        detail={"name": rule.name, "priority": rule.priority},
        client_ip=current_ip(request),
    )
    db.commit()
    return {"id": rule.id, "message": MSG_RULE_CREATED}


def update_rule(db: Session, rule_id: int, payload: dict, user: User, request: Request) -> dict:
    rule = source_service.update_rule(db, rule_id, payload)
    audit_service.record(
        db,
        user=user,
        action="parse_rules.update",
        entity="parse_rule",
        entity_id=str(rule.id),
        detail={key: str(value) for key, value in payload.items()},
        client_ip=current_ip(request),
    )
    db.commit()
    return {"id": rule.id, "enabled": bool(rule.enabled), "message": MSG_RULE_UPDATED}
