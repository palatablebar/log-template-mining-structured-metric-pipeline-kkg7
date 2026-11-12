"""日志源与解析规则领域逻辑。"""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.models.base import now_local
from src.models.log_event import LogEvent
from src.models.log_source import LogSource
from src.models.log_template import LogTemplate
from src.models.parse_rule import ParseRule
from src.utils.errors import AppError


def _validate_regex(pattern: str) -> None:
    if not pattern.strip():
        raise AppError(codes.RULE_INVALID_REGEX, "正则不能为空", "empty pattern")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise AppError(codes.RULE_INVALID_REGEX, "解析规则正则无法编译", str(exc)) from exc


def list_sources(db: Session) -> list[dict]:
    sources = db.execute(select(LogSource).order_by(LogSource.id)).scalars().all()
    rule_counts = dict(
        db.execute(select(ParseRule.source_id, func.count()).group_by(ParseRule.source_id)).all()
    )
    template_counts = dict(
        db.execute(
            select(LogTemplate.source_id, func.count())
            .where(LogTemplate.is_noise.is_(False))
            .group_by(LogTemplate.source_id)
        ).all()
    )
    event_counts = dict(db.execute(select(LogEvent.source_id, func.count()).group_by(LogEvent.source_id)).all())
    pending_counts = dict(
        db.execute(
            select(LogEvent.source_id, func.count())
            .where(LogEvent.template_id.is_(None))
            .group_by(LogEvent.source_id)
        ).all()
    )
    return [
        {
            "id": source.id,
            "name": source.name,
            "service": source.service,
            "log_format": source.log_format,
            "collect_status": source.collect_status,
            "rate_per_min": source.rate_per_min,
            "host_group": source.host_group,
            "description": source.description,
            "last_collected_at": source.last_collected_at.isoformat(sep=" ") if source.last_collected_at else None,
            "rule_count": int(rule_counts.get(source.id, 0)),
            "template_count": int(template_counts.get(source.id, 0)),
            "event_count": int(event_counts.get(source.id, 0)),
            "pending_count": int(pending_counts.get(source.id, 0)),
        }
        for source in sources
    ]


def create_source(db: Session, payload: dict) -> LogSource:
    name = payload["name"].strip()
    exists = db.execute(select(LogSource).where(LogSource.name == name)).scalar_one_or_none()
    if exists is not None:
        raise AppError(codes.SOURCE_NAME_DUPLICATED, f"日志源 {name} 已存在", f"name={name}")
    source = LogSource(
        name=name,
        service=payload.get("service") or name,
        log_format=payload.get("log_format", "plain"),
        collect_status=payload.get("collect_status", "active"),
        rate_per_min=int(payload.get("rate_per_min", 0)),
        host_group=payload.get("host_group", ""),
        description=payload.get("description", ""),
        last_collected_at=now_local(),
    )
    db.add(source)
    db.flush()
    return source


def update_source(db: Session, source_id: int, payload: dict) -> LogSource:
    source = db.get(LogSource, source_id)
    if source is None:
        raise AppError(codes.SOURCE_NOT_FOUND, "日志源不存在", f"source_id={source_id}")
    for field in ("collect_status", "rate_per_min", "host_group", "description", "log_format"):
        if field in payload and payload[field] is not None:
            setattr(source, field, payload[field])
    db.flush()
    return source


def list_rules(db: Session, source_id: int | None = None) -> list[dict]:
    query = select(ParseRule).order_by(ParseRule.source_id, ParseRule.priority)
    if source_id is not None:
        query = query.where(ParseRule.source_id == source_id)
    rules = db.execute(query).scalars().all()
    source_names = dict(db.execute(select(LogSource.id, LogSource.name)).all())
    return [
        {
            "id": rule.id,
            "source_id": rule.source_id,
            "source_name": source_names.get(rule.source_id, ""),
            "name": rule.name,
            "pattern": rule.pattern,
            "field_names": list(rule.field_names or []),
            "priority": rule.priority,
            "enabled": bool(rule.enabled),
            "hit_count": rule.hit_count,
        }
        for rule in rules
    ]


def create_rule(db: Session, source_id: int, payload: dict) -> ParseRule:
    source = db.get(LogSource, source_id)
    if source is None:
        raise AppError(codes.SOURCE_NOT_FOUND, "日志源不存在", f"source_id={source_id}")
    _validate_regex(payload["pattern"])
    rule = ParseRule(
        source_id=source_id,
        name=payload["name"].strip(),
        pattern=payload["pattern"],
        field_names=list(payload.get("field_names") or []),
        priority=int(payload.get("priority", 100)),
        enabled=bool(payload.get("enabled", True)),
    )
    db.add(rule)
    db.flush()
    return rule


def update_rule(db: Session, rule_id: int, payload: dict) -> ParseRule:
    rule = db.get(ParseRule, rule_id)
    if rule is None:
        raise AppError(codes.NOT_FOUND, "解析规则不存在", f"rule_id={rule_id}")
    if payload.get("pattern"):
        _validate_regex(payload["pattern"])
        rule.pattern = payload["pattern"]
    for field in ("name", "priority", "enabled", "field_names"):
        if field in payload and payload[field] is not None:
            setattr(rule, field, payload[field])
    db.flush()
    return rule


def serialize_rule(rule: ParseRule) -> dict:
    return {
        "id": rule.id,
        "source_id": rule.source_id,
        "name": rule.name,
        "pattern": rule.pattern,
        "field_names": list(rule.field_names or []),
        "priority": rule.priority,
        "enabled": bool(rule.enabled),
        "hit_count": rule.hit_count,
    }
