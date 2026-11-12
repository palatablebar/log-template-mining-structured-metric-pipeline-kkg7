"""元信息：枚举下发、概览指标、健康检查。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.database import ping_db
from src.constants.enums import (
    AlertMetric,
    AlertStatus,
    CollectStatus,
    EventLevel,
    LogFormat,
    TemplateStatus,
    TriggerReason,
)
from src.constants.roles import PERMISSIONS
from src.models.alert_event import AlertEvent
from src.models.log_event import LogEvent
from src.models.log_source import LogSource
from src.models.log_template import LogTemplate
from src.models.parse_rule import ParseRule
from src.services import alert_service, template_service
from src.utils.redis_client import redis_ping


def enums() -> dict:
    return {
        "roles": ["admin", "engineer", "viewer"],
        "log_formats": [item.value for item in LogFormat],
        "collect_status": [item.value for item in CollectStatus],
        "template_status": [item.value for item in TemplateStatus],
        "slot_types": ["num", "ip", "uuid", "path", "hex", "ts", "str", "unknown"],
        "event_levels": [item.value for item in EventLevel],
        "trigger_reasons": [item.value for item in TriggerReason],
        "alert_status": [item.value for item in AlertStatus],
        "alert_metrics": [item.value for item in AlertMetric],
        "permissions": {action: list(roles) for action, roles in PERMISSIONS.items()},
    }


def health(db: Session) -> dict:
    return {
        "status": "ok" if ping_db() else "degraded",
        "database": "ok" if ping_db() else "down",
        "redis": "ok" if redis_ping() else "down",
        "service": "logmine-backend",
        "version": "1.0.0",
    }


def overview(db: Session) -> dict:
    template_stats = template_service.overview(db)
    events_total = int(db.execute(select(func.count()).select_from(LogEvent)).scalar_one())
    pending = int(
        db.execute(select(func.count()).select_from(LogEvent).where(LogEvent.template_id.is_(None))).scalar_one()
    )
    sources = int(db.execute(select(func.count()).select_from(LogSource)).scalar_one())
    rules = int(db.execute(select(func.count()).select_from(ParseRule)).scalar_one())
    alerts = alert_service.stats(db)
    anchor = db.execute(select(func.max(LogEvent.bucket_start))).scalar_one_or_none()
    covered = events_total - pending
    return {
        "sources": sources,
        "parse_rules": rules,
        "templates": template_stats["templates"],
        "noise_templates": template_stats["noise"],
        "tentative_templates": template_stats["tentative"],
        "slots": template_stats["slots"],
        "events": events_total,
        "pending_events": pending,
        "covered_events": covered,
        "coverage_percent": round(covered / events_total * 100, 2) if events_total else 0.0,
        "alerts": alerts,
        "anchor": anchor.isoformat(sep=" ") if anchor else None,
    }
