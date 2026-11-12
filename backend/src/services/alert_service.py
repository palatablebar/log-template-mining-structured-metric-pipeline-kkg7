"""告警规则与触发记录：异常扫描（算法 B 落库）、确认、静默。"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import AlertMetric, AlertStatus, EventLevel, TriggerReason
from src.models.alert_event import AlertEvent
from src.models.alert_rule import AlertRule
from src.models.base import now_local
from src.models.log_event import LogEvent
from src.models.log_template import LogTemplate
from src.services import anomaly_engine as engine
from src.services.audit_service import record as audit_record
from src.utils.errors import AppError
from src.utils.logger import get_logger
from src.utils.time_buckets import BUCKET_MINUTES, bucket_start, last_n_buckets

logger = get_logger("logmine.alert")

ERROR_LEVELS = (EventLevel.ERROR.value, EventLevel.FATAL.value)
DEFAULT_SILENCE_MINUTES = 30


def serialize_rule(rule: AlertRule, template_str: str = "") -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "template_id": rule.template_id,
        "template_str": template_str,
        "metric": rule.metric,
        "window_minutes": rule.window_minutes,
        "baseline_buckets": rule.baseline_buckets,
        "z_threshold": rule.z_threshold,
        "error_ratio_low": rule.error_ratio_low,
        "error_ratio_high": rule.error_ratio_high,
        "silence_minutes": rule.silence_minutes,
        "enabled": bool(rule.enabled),
        "description": rule.description,
        "created_by": rule.created_by,
    }


def serialize_alert(db: Session, alert: AlertEvent, template: LogTemplate | None = None) -> dict:
    return {
        "id": alert.id,
        "rule_id": alert.rule_id,
        "template_id": alert.template_id,
        "template_str": template.template_str if template else "",
        "service": template.service if template else "",
        "bucket_start": alert.bucket_start.isoformat(sep=" "),
        "triggered_at": alert.triggered_at.isoformat(sep=" "),
        "count_in_bucket": alert.count_in_bucket,
        "baseline_median": round(alert.baseline_median, 4),
        "baseline_mad": round(alert.baseline_mad, 4),
        "z_score": round(alert.z_score, 4),
        "error_ratio": round(alert.error_ratio, 4),
        "baseline_error_ratio": round(alert.baseline_error_ratio, 4),
        "level": alert.level,
        "reason": alert.reason,
        "status": alert.status,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": alert.acknowledged_at.isoformat(sep=" ") if alert.acknowledged_at else None,
        "silenced_until": alert.silenced_until.isoformat(sep=" ") if alert.silenced_until else None,
        "note": alert.note,
        "origin": alert.origin,
    }


def list_rules(db: Session) -> list[dict]:
    rules = db.execute(select(AlertRule).order_by(AlertRule.id)).scalars().all()
    template_strs = dict(db.execute(select(LogTemplate.id, LogTemplate.template_str)).all())
    return [serialize_rule(rule, template_strs.get(rule.template_id or -1, "")) for rule in rules]


def create_rule(db: Session, payload: dict, actor: str) -> AlertRule:
    template_id = payload.get("template_id")
    if template_id is not None and db.get(LogTemplate, template_id) is None:
        raise AppError(codes.TEMPLATE_NOT_FOUND, "模板不存在", f"template_id={template_id}")
    rule = AlertRule(
        name=payload["name"].strip(),
        template_id=template_id,
        metric=payload.get("metric", AlertMetric.BOTH.value),
        window_minutes=int(payload.get("window_minutes", BUCKET_MINUTES)),
        baseline_buckets=int(payload.get("baseline_buckets", 12)),
        z_threshold=float(payload.get("z_threshold", 3.5)),
        error_ratio_low=float(payload.get("error_ratio_low", 0.05)),
        error_ratio_high=float(payload.get("error_ratio_high", 0.25)),
        silence_minutes=int(payload.get("silence_minutes", DEFAULT_SILENCE_MINUTES)),
        enabled=bool(payload.get("enabled", True)),
        description=payload.get("description", ""),
        created_by=actor,
    )
    db.add(rule)
    db.flush()
    return rule


def update_rule(db: Session, rule_id: int, payload: dict) -> AlertRule:
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise AppError(codes.NOT_FOUND, "告警规则不存在", f"rule_id={rule_id}")
    for field in (
        "name",
        "metric",
        "window_minutes",
        "baseline_buckets",
        "z_threshold",
        "error_ratio_low",
        "error_ratio_high",
        "silence_minutes",
        "enabled",
        "description",
    ):
        if field in payload and payload[field] is not None:
            setattr(rule, field, payload[field])
    db.flush()
    return rule


def list_alerts(db: Session, *, status: str | None = None, limit: int = 100) -> list[dict]:
    query = select(AlertEvent).order_by(AlertEvent.triggered_at.desc(), AlertEvent.id.desc())
    if status:
        query = query.where(AlertEvent.status == status)
    alerts = db.execute(query.limit(limit)).scalars().all()
    templates = {
        template.id: template
        for template in db.execute(
            select(LogTemplate).where(LogTemplate.id.in_([alert.template_id for alert in alerts] or [0]))
        )
        .scalars()
        .all()
    }
    return [serialize_alert(db, alert, templates.get(alert.template_id)) for alert in alerts]


def _rule_for_template(rule_map: dict, template_id: int) -> engine.RuleConfig | None:
    specific = rule_map.get(("template", template_id))
    global_rule = rule_map.get(("global", 0))
    chosen = specific or global_rule
    return chosen


def _build_rule_config(rule: AlertRule) -> engine.RuleConfig:
    return engine.RuleConfig(
        rule_id=rule.id,
        metric=rule.metric,
        baseline_buckets=rule.baseline_buckets,
        z_threshold=rule.z_threshold,
        error_ratio_low=rule.error_ratio_low,
        error_ratio_high=rule.error_ratio_high,
        silence_minutes=rule.silence_minutes,
    )


def _debounced(db: Session, template_id: int, anchor: datetime) -> bool:
    """去抖：同模板最近一条告警仍在静默窗口内（silenced_until 为空时按 triggered_at+30min 兜底）。"""
    latest = db.execute(
        select(AlertEvent)
        .where(
            AlertEvent.template_id == template_id,
            AlertEvent.status.in_(
                (AlertStatus.FIRING.value, AlertStatus.ACKNOWLEDGED.value, AlertStatus.SILENCED.value)
            ),
        )
        .order_by(AlertEvent.triggered_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest is None:
        return False
    silenced_until = latest.silenced_until or (latest.triggered_at + timedelta(minutes=DEFAULT_SILENCE_MINUTES))
    return silenced_until > anchor


def run_scan(db: Session, *, origin: str = "manual", persist: bool = True, actor: str = "") -> dict:
    """执行一次异常扫描：对齐到全局最新 5min 桶，逐模板判定并落 alert_event。"""
    started = time.perf_counter()
    rules = db.execute(select(AlertRule).where(AlertRule.enabled.is_(True))).scalars().all()
    if not rules:
        return {
            "bucket": None,
            "templates_scanned": 0,
            "alerts": [],
            "created": 0,
            "skipped": [],
            "insufficient_history": 0,
            "elapsed_ms": 0,
            "message": "没有启用的告警规则",
        }

    rule_map: dict[tuple[str, int], engine.RuleConfig] = {}
    rule_objects: dict[int, AlertRule] = {}
    for rule in rules:
        config = _build_rule_config(rule)
        rule_objects[rule.id] = rule
        if rule.template_id is None:
            rule_map.setdefault(("global", 0), config)
        else:
            rule_map[("template", rule.template_id)] = config

    anchor_row = db.execute(select(func.max(LogEvent.bucket_start))).scalar_one_or_none()
    if anchor_row is None:
        return {
            "bucket": None,
            "templates_scanned": 0,
            "alerts": [],
            "created": 0,
            "skipped": [],
            "insufficient_history": 0,
            "elapsed_ms": 0,
            "message": "还没有任何事件，先导入日志",
        }
    anchor = bucket_start(anchor_row)
    window = last_n_buckets(anchor, engine.BASELINE_BUCKETS + 1)
    window_start = window[0]

    rows = db.execute(
        select(
            LogEvent.template_id,
            LogEvent.bucket_start,
            func.count(LogEvent.id),
            func.sum(case((LogEvent.level.in_(ERROR_LEVELS), 1), else_=0)),
        )
        .where(
            LogEvent.template_id.is_not(None),
            LogEvent.bucket_start.is_not(None),
            LogEvent.bucket_start >= window_start,
            LogEvent.bucket_start <= anchor,
        )
        .group_by(LogEvent.template_id, LogEvent.bucket_start)
    ).all()

    templates = {
        template.id: template
        for template in db.execute(
            select(LogTemplate).where(
                LogTemplate.id.in_([int(row[0]) for row in rows] or [0]), LogTemplate.is_noise.is_(False)
            )
        )
        .scalars()
        .all()
    }

    counts_by_template: dict[int, dict[datetime, tuple[int, int]]] = {}
    for template_id, bucket_at, count, errors in rows:
        template_id = int(template_id)
        if template_id not in templates:
            continue
        counts_by_template.setdefault(template_id, {})[bucket_at] = (int(count or 0), int(errors or 0))

    series_by_template: dict[int, tuple[str, str, list[tuple[datetime, int, int]]]] = {}
    for template_id, template in templates.items():
        bucket_counts = counts_by_template.get(template_id, {})
        raw_series = [
            (bucket, *bucket_counts.get(bucket, (0, 0)))  # 缺桶补 0
            for bucket in window
        ]
        series_by_template[template_id] = (template.template_str, template.service, raw_series)

    scan_result = engine.scan_series(series_by_template, lambda tid: _rule_for_template(rule_map, tid))
    created = 0
    created_alerts: list[dict] = []
    for candidate in scan_result.alerts:
        if _debounced(db, candidate.template_id, anchor):
            continue
        config = _rule_for_template(rule_map, candidate.template_id)
        rule_id = config.rule_id if config and config.rule_id else rules[0].id
        rule_obj = rule_objects.get(rule_id) or rules[0]
        alert = AlertEvent(
            rule_id=rule_obj.id,
            template_id=candidate.template_id,
            bucket_start=candidate.bucket_start,
            count_in_bucket=candidate.count,
            baseline_median=candidate.baseline_median,
            baseline_mad=candidate.baseline_mad,
            z_score=candidate.z_score,
            error_ratio=candidate.error_ratio,
            baseline_error_ratio=candidate.baseline_error_ratio,
            level=candidate.level,
            reason=candidate.reason,
            status=AlertStatus.FIRING.value,
            triggered_at=candidate.bucket_start,
            silenced_until=candidate.bucket_start + timedelta(minutes=rule_obj.silence_minutes),
            note="",
            origin=origin,
        )
        db.add(alert)
        db.flush()
        created += 1
        created_alerts.append(serialize_alert(db, alert, templates.get(candidate.template_id)))
        logger.warning(
            "anomaly.alert template_id=%s count=%s z=%.3f reason=%s",
            candidate.template_id,
            candidate.count,
            candidate.z_score,
            candidate.reason,
        )

    if actor and created:
        audit_record(
            db,
            user=None,
            actor_email=actor,
            action="alerts.scan",
            entity="alert_event",
            entity_id=",".join(str(item["id"]) for item in created_alerts),
            detail={"created": created, "bucket": anchor.isoformat(sep=" ")},
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    payload = scan_result.to_dict()
    payload["created"] = created
    payload["created_alerts"] = created_alerts
    payload["elapsed_ms"] = elapsed_ms
    logger.info(
        "anomaly.scan templates=%s alerts=%s created=%s skipped=%s",
        scan_result.templates_scanned,
        len(scan_result.alerts),
        created,
        len(scan_result.skipped),
    )
    return payload


def acknowledge(db: Session, alert_id: int, actor: str, note: str = "", silence_minutes: int | None = None) -> dict:
    alert = db.get(AlertEvent, alert_id)
    if alert is None:
        raise AppError(codes.NOT_FOUND, "告警记录不存在", f"alert_id={alert_id}")
    if alert.status == AlertStatus.ACKNOWLEDGED.value and silence_minutes is None:
        raise AppError(codes.ALERT_ALREADY_ACKED, "该告警已被确认", f"alert_id={alert_id}")
    alert.status = AlertStatus.ACKNOWLEDGED.value
    alert.acknowledged_by = actor
    alert.acknowledged_at = now_local()
    alert.note = note or alert.note
    if silence_minutes:
        alert.status = AlertStatus.SILENCED.value
        alert.silenced_until = now_local() + timedelta(minutes=silence_minutes)
    db.flush()
    return serialize_alert(db, alert, db.get(LogTemplate, alert.template_id))


def silence(db: Session, alert_id: int, actor: str, minutes: int = DEFAULT_SILENCE_MINUTES, note: str = "") -> dict:
    alert = db.get(AlertEvent, alert_id)
    if alert is None:
        raise AppError(codes.NOT_FOUND, "告警记录不存在", f"alert_id={alert_id}")
    alert.status = AlertStatus.SILENCED.value
    alert.acknowledged_by = alert.acknowledged_by or actor
    alert.acknowledged_at = alert.acknowledged_at or now_local()
    alert.silenced_until = now_local() + timedelta(minutes=max(1, minutes))
    if note:
        alert.note = note
    db.flush()
    return serialize_alert(db, alert, db.get(LogTemplate, alert.template_id))


def stats(db: Session) -> dict:
    rows = db.execute(select(AlertEvent.status, func.count()).group_by(AlertEvent.status)).all()
    by_status = {row[0]: int(row[1]) for row in rows}
    total = sum(by_status.values())
    return {
        "total": total,
        "firing": by_status.get(AlertStatus.FIRING.value, 0),
        "acknowledged": by_status.get(AlertStatus.ACKNOWLEDGED.value, 0),
        "silenced": by_status.get(AlertStatus.SILENCED.value, 0),
        "resolved": by_status.get(AlertStatus.RESOLVED.value, 0),
    }


def formula() -> dict:
    payload = engine.describe_formula()
    payload["reasons"] = [item.value for item in TriggerReason]
    return payload
