"""告警规则与触发记录：异常扫描（算法 B 落库）、确认、静默、补传补算。"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import AlertMetric, AlertStatus, EventLevel, RecomputeAction, TriggerReason
from src.constants.limits import MAX_RECOMPUTE_PAIRS, MAX_RECOMPUTE_RANGE_HOURS
from src.models.alert_event import AlertEvent
from src.models.alert_recompute import AlertRecomputeDetail, AlertRecomputeJob
from src.models.alert_rule import AlertRule
from src.models.base import now_local
from src.models.log_event import LogEvent
from src.models.log_template import LogTemplate
from src.services import anomaly_engine as engine
from src.services.audit_service import record as audit_record
from src.utils.errors import AppError
from src.utils.logger import get_logger
from src.utils.time_buckets import BUCKET_MINUTES, bucket_start, last_n_buckets, parse_log_time

logger = get_logger("logmine.alert")

ERROR_LEVELS = (EventLevel.ERROR.value, EventLevel.FATAL.value)
DEFAULT_SILENCE_MINUTES = 30
# 补算重算的下游窗口：基线取目标桶前 12 桶，补传桶之后 12 个桶的基线都会受影响
RECOMPUTE_DOWNSTREAM_BUCKETS = engine.BASELINE_BUCKETS
ACTIVE_ALERT_STATUSES = (
    AlertStatus.FIRING.value,
    AlertStatus.ACKNOWLEDGED.value,
    AlertStatus.SILENCED.value,
)


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
        "recompute_count": alert.recompute_count,
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
    # 同 (模板, 桶) 唯一：扫描命中已存在的告警时不重复插入（补算可能已为该桶建过记录）
    existing_keys = {
        (row[0], row[1])
        for row in db.execute(
            select(AlertEvent.template_id, AlertEvent.bucket_start).where(
                AlertEvent.bucket_start == anchor
            )
        ).all()
    }
    created = 0
    created_alerts: list[dict] = []
    for candidate in scan_result.alerts:
        if _debounced(db, candidate.template_id, anchor):
            continue
        if (candidate.template_id, candidate.bucket_start) in existing_keys:
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


def _bucket_counts(
    db: Session, template_ids: list[int], window_start: datetime, window_end: datetime
) -> dict[int, dict[datetime, tuple[int, int]]]:
    """取若干模板在 [window_start, window_end] 内按桶的 (计数, error 计数)。"""
    if not template_ids:
        return {}
    rows = db.execute(
        select(
            LogEvent.template_id,
            LogEvent.bucket_start,
            func.count(LogEvent.id),
            func.sum(case((LogEvent.level.in_(ERROR_LEVELS), 1), else_=0)),
        )
        .where(
            LogEvent.template_id.in_(template_ids),
            LogEvent.bucket_start.is_not(None),
            LogEvent.bucket_start >= window_start,
            LogEvent.bucket_start <= window_end,
        )
        .group_by(LogEvent.template_id, LogEvent.bucket_start)
    ).all()
    result: dict[int, dict[datetime, tuple[int, int]]] = {}
    for template_id, bucket_at, count, errors in rows:
        result.setdefault(int(template_id), {})[bucket_at] = (int(count or 0), int(errors or 0))
    return result


def _enabled_rule_map(db: Session) -> tuple[dict, dict, list[AlertRule]]:
    """启用中的规则 → (rule_map, rule_objects, rules)；与 run_scan 同构。"""
    rules = db.execute(select(AlertRule).where(AlertRule.enabled.is_(True))).scalars().all()
    rule_map: dict[tuple[str, int], engine.RuleConfig] = {}
    rule_objects: dict[int, AlertRule] = {}
    for rule in rules:
        config = _build_rule_config(rule)
        rule_objects[rule.id] = rule
        if rule.template_id is None:
            rule_map.setdefault(("global", 0), config)
        else:
            rule_map[("template", rule.template_id)] = config
    return rule_map, rule_objects, rules


def _resolve_recompute_scope(
    db: Session,
    *,
    start: datetime | None,
    end: datetime | None,
    template_ids: list[int] | None,
) -> dict:
    """解析补算范围 → 受影响 (模板, 桶) 集合与受影响桶列表。

    自动范围（不给 start/end）：取导入事件（origin='import'）覆盖的桶；
    下游扩展：补传桶之后 BASELINE_BUCKETS 个桶的基线会被改写，同样纳入。
    模板集合：范围内有事件的模板 ∪ 范围内已有告警的模板；显式 template_ids 取交集。
    """
    import_bounds = db.execute(
        select(func.min(LogEvent.bucket_start), func.max(LogEvent.bucket_start)).where(
            LogEvent.origin == "import", LogEvent.bucket_start.is_not(None)
        )
    ).one()
    auto_start = bucket_start(import_bounds[0]) if import_bounds[0] else None
    auto_end = bucket_start(import_bounds[1]) if import_bounds[1] else None

    if start is None and end is None:
        range_start, range_end = auto_start, auto_end
    else:
        range_start = bucket_start(start) if start else auto_start
        range_end = bucket_start(end) if end else auto_end
    if range_start is None or range_end is None:
        return {
            "range_start": None,
            "range_end": None,
            "pairs": [],
            "buckets": [],
            "template_ids": [],
            "auto": start is None and end is None,
        }
    if range_end < range_start:
        raise AppError(codes.VALIDATION_ERROR, "补算结束时间不能早于开始时间", f"{range_start} > {range_end}")
    max_span = timedelta(hours=MAX_RECOMPUTE_RANGE_HOURS)
    if range_end - range_start > max_span:
        raise AppError(
            codes.VALIDATION_ERROR,
            f"补算范围不能超过 {MAX_RECOMPUTE_RANGE_HOURS} 小时",
            f"{range_start} ~ {range_end}",
        )

    # 下游扩展到 range_end + 12 桶（基线窗口宽度），但不超过库内最新桶
    latest_row = db.execute(select(func.max(LogEvent.bucket_start))).scalar_one_or_none()
    latest = bucket_start(latest_row) if latest_row else range_end
    expanded_end = min(latest, range_end + timedelta(minutes=BUCKET_MINUTES * RECOMPUTE_DOWNSTREAM_BUCKETS))

    event_pairs = db.execute(
        select(LogEvent.template_id, LogEvent.bucket_start)
        .where(
            LogEvent.template_id.is_not(None),
            LogEvent.bucket_start.is_not(None),
            LogEvent.bucket_start >= range_start,
            LogEvent.bucket_start <= expanded_end,
        )
        .distinct()
    ).all()
    alert_pairs = db.execute(
        select(AlertEvent.template_id, AlertEvent.bucket_start).where(
            AlertEvent.bucket_start >= range_start,
            AlertEvent.bucket_start <= expanded_end,
        )
    ).all()
    pair_set: set[tuple[int, datetime]] = {
        (int(tid), bucket_start(bkt)) for tid, bkt in event_pairs
    }
    pair_set.update((int(tid), bucket_start(bkt)) for tid, bkt in alert_pairs)

    if template_ids:
        wanted = {int(item) for item in template_ids}
        pair_set = {pair for pair in pair_set if pair[0] in wanted}

    affected_templates = sorted({tid for tid, _ in pair_set})
    affected_buckets = sorted({bkt for _, bkt in pair_set})
    pairs = sorted(pair_set, key=lambda item: (item[1], item[0]))
    return {
        "range_start": range_start,
        "range_end": range_end,
        "expanded_end": expanded_end,
        "pairs": pairs,
        "buckets": affected_buckets,
        "template_ids": affected_templates,
        "auto": start is None and end is None,
    }


def _candidate_snapshot(candidate: engine.AlertCandidate) -> dict:
    return {
        "count": candidate.count,
        "baseline_median": candidate.baseline_median,
        "baseline_mad": candidate.baseline_mad,
        "z_score": candidate.z_score,
        "error_ratio": candidate.error_ratio,
        "baseline_error_ratio": candidate.baseline_error_ratio,
        "level": candidate.level,
        "reason": candidate.reason,
    }


def _alert_snapshot(alert: AlertEvent | None) -> dict | None:
    if alert is None:
        return None
    return {
        "status": alert.status,
        "count": alert.count_in_bucket,
        "z_score": alert.z_score,
        "error_ratio": alert.error_ratio,
    }


def _parse_optional_moment(value: str | datetime | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    parsed = parse_log_time(value)
    if parsed is None:
        raise AppError(codes.VALIDATION_ERROR, f"无法解析时间: {value}", value)
    return parsed


def recompute_preview(
    db: Session,
    *,
    start: str | datetime | None = None,
    end: str | datetime | None = None,
    template_ids: list[int] | None = None,
) -> dict:
    """只算受影响范围，不落库：给告警页发起补算前确认用。"""
    start_dt = _parse_optional_moment(start)
    end_dt = _parse_optional_moment(end)
    scope = _resolve_recompute_scope(db, start=start_dt, end=end_dt, template_ids=template_ids)
    if not scope["pairs"]:
        return {
            "range_start": None,
            "range_end": None,
            "auto": scope["auto"],
            "bucket_count": 0,
            "template_count": 0,
            "pair_count": 0,
            "buckets": [],
            "message": "没有可补算的受影响模板与时间桶（先补传日志并应用模板）",
        }
    return {
        "range_start": scope["range_start"].isoformat(sep=" "),
        "range_end": scope["range_end"].isoformat(sep=" "),
        "expanded_end": scope["expanded_end"].isoformat(sep=" "),
        "auto": scope["auto"],
        "bucket_count": len(scope["buckets"]),
        "template_count": len(scope["template_ids"]),
        "pair_count": len(scope["pairs"]),
        "buckets": [item.isoformat(sep=" ") for item in scope["buckets"]],
        "template_ids": scope["template_ids"],
    }


def run_recompute(
    db: Session,
    *,
    actor: str,
    start: str | datetime | None = None,
    end: str | datetime | None = None,
    template_ids: list[int] | None = None,
    idempotency_key: str = "",
    note: str = "",
) -> dict:
    """补传补算：只重算受影响的 (模板, 时间桶)。

    - 仍命中：更新判定数据，保留原确认（acknowledged_*）与静默（silenced_until、状态）；
    - 不再命中：已有告警转为 resolved，确认/静默痕迹保留；
    - 新命中：补建告警（不走去抖，补算就是补历史判定）；
    - 同一 (模板, 桶) 只有一条告警，重复投递同一批日志幂等，不新增告警。
    """
    started = time.perf_counter()
    start_dt = _parse_optional_moment(start)
    end_dt = _parse_optional_moment(end)
    rule_map, rule_objects, rules = _enabled_rule_map(db)
    if not rules:
        return {
            "id": None,
            "deduplicated": False,
            "message": "没有启用的告警规则",
            "created": 0,
            "updated": 0,
            "resolved": 0,
            "unchanged": 0,
            "skipped": 0,
            "details": [],
        }

    scope = _resolve_recompute_scope(db, start=start_dt, end=end_dt, template_ids=template_ids)
    pairs: list[tuple[int, datetime]] = scope["pairs"]
    if not pairs:
        return {
            "id": None,
            "deduplicated": False,
            "range_start": None,
            "range_end": None,
            "message": "没有可补算的受影响模板与时间桶（先补传日志并应用模板）",
            "created": 0,
            "updated": 0,
            "resolved": 0,
            "unchanged": 0,
            "skipped": 0,
            "details": [],
        }
    if len(pairs) > MAX_RECOMPUTE_PAIRS:
        raise AppError(
            codes.VALIDATION_ERROR,
            f"受影响 (模板×桶) 共 {len(pairs)} 个，超过单次上限 {MAX_RECOMPUTE_PAIRS}，请缩小时间范围",
            f"pairs={len(pairs)}",
        )

    range_start: datetime = scope["range_start"]
    expanded_end: datetime = scope["expanded_end"]
    if not idempotency_key:
        digest_source = "|".join(
            [range_start.isoformat(), expanded_end.isoformat(), ",".join(map(str, scope["template_ids"]))]
        )
        idempotency_key = "rc-" + hashlib.sha1(digest_source.encode("utf-8")).hexdigest()[:16]
    existing_job = db.execute(
        select(AlertRecomputeJob).where(AlertRecomputeJob.idempotency_key == idempotency_key)
    ).scalar_one_or_none()
    if existing_job is not None:
        logger.info("recompute.deduplicated key=%s job_id=%s", idempotency_key, existing_job.id)
        return {
            **serialize_job(db, existing_job),
            "deduplicated": True,
            "message": "同一范围的补算已执行过，直接返回上次结果，未新增告警",
        }

    affected_template_ids = scope["template_ids"]
    templates = {
        item.id: item
        for item in db.execute(
            select(LogTemplate).where(
                LogTemplate.id.in_(affected_template_ids or [0]), LogTemplate.is_noise.is_(False)
            )
        ).scalars().all()
    }
    # 计数窗口要覆盖最早目标桶的基线（前 12 桶）
    window_start = range_start - timedelta(minutes=BUCKET_MINUTES * engine.BASELINE_BUCKETS)
    counts = _bucket_counts(db, affected_template_ids, window_start, expanded_end)

    existing_alerts: dict[tuple[int, datetime], AlertEvent] = {
        (alert.template_id, alert.bucket_start): alert
        for alert in db.execute(
            select(AlertEvent).where(
                AlertEvent.template_id.in_(affected_template_ids or [0]),
                AlertEvent.bucket_start >= range_start,
                AlertEvent.bucket_start <= expanded_end,
            )
        ).scalars().all()
    }

    job = AlertRecomputeJob(
        idempotency_key=idempotency_key,
        triggered_by=actor,
        range_start=range_start,
        range_end=scope["range_end"],
        affected_bucket_count=len(scope["buckets"]),
        affected_template_count=len(affected_template_ids),
        pair_count=len(pairs),
        note=note,
    )
    db.add(job)
    db.flush()

    counters = {"created": 0, "updated": 0, "resolved": 0, "unchanged": 0, "skipped": 0}
    details: list[dict] = []

    for template_id, target_bucket in pairs:
        template = templates.get(template_id)
        if template is None:
            continue
        config = _rule_for_template(rule_map, template_id)
        if config is None:
            continue
        rule_obj = rule_objects.get(config.rule_id) if config.rule_id else rules[0]
        before_alert = existing_alerts.get((template_id, target_bucket))
        before_snapshot = _alert_snapshot(before_alert)
        outcome = engine.evaluate_bucket(
            template_id,
            template.template_str,
            counts.get(template_id, {}),
            target_bucket,
            config,
            template.service,
        )

        action = RecomputeAction.UNCHANGED.value
        after_snapshot: dict | None = None
        alert_id = before_alert.id if before_alert else None
        detail_note = ""

        if isinstance(outcome, engine.AlertCandidate):
            snap = _candidate_snapshot(outcome)
            after_snapshot = snap
            if before_alert is None:
                action = RecomputeAction.CREATED.value
                alert = AlertEvent(
                    rule_id=rule_obj.id,
                    template_id=template_id,
                    bucket_start=target_bucket,
                    count_in_bucket=snap["count"],
                    baseline_median=snap["baseline_median"],
                    baseline_mad=snap["baseline_mad"],
                    z_score=snap["z_score"],
                    error_ratio=snap["error_ratio"],
                    baseline_error_ratio=snap["baseline_error_ratio"],
                    level=snap["level"],
                    reason=snap["reason"],
                    status=AlertStatus.FIRING.value,
                    triggered_at=target_bucket,
                    silenced_until=target_bucket + timedelta(minutes=rule_obj.silence_minutes),
                    note="",
                    origin="recompute",
                    recompute_count=0,
                )
                db.add(alert)
                db.flush()
                alert_id = alert.id
                after_snapshot = _alert_snapshot(alert)
                counters["created"] += 1
                logger.warning(
                    "recompute.create template_id=%s bucket=%s count=%s z=%.3f",
                    template_id,
                    target_bucket,
                    snap["count"],
                    snap["z_score"],
                )
            else:
                # 仍命中：只刷新判定数据；确认/静默字段与人工状态原样保留
                before_alert.rule_id = rule_obj.id
                before_alert.count_in_bucket = snap["count"]
                before_alert.baseline_median = snap["baseline_median"]
                before_alert.baseline_mad = snap["baseline_mad"]
                before_alert.z_score = snap["z_score"]
                before_alert.error_ratio = snap["error_ratio"]
                before_alert.baseline_error_ratio = snap["baseline_error_ratio"]
                before_alert.level = snap["level"]
                before_alert.reason = snap["reason"]
                if before_alert.status == AlertStatus.RESOLVED.value:
                    # 曾被补算恢复、如今重新命中：再次触发，确认/静默痕迹仍保留在原字段
                    before_alert.status = AlertStatus.FIRING.value
                    detail_note = "resolved 后重新命中"
                before_alert.origin = "recompute"
                before_alert.recompute_count = (before_alert.recompute_count or 0) + 1
                action = RecomputeAction.UPDATED.value
                after_snapshot = _alert_snapshot(before_alert)
                counters["updated"] += 1
        else:
            # 不再命中（within_baseline / insufficient_history）
            if before_alert is not None:
                if outcome.reason == "insufficient_history":
                    action = RecomputeAction.SKIPPED.value
                    detail_note = "历史桶不足，保留原告警不动"
                    after_snapshot = before_snapshot
                    counters["skipped"] += 1
                else:
                    action = RecomputeAction.RESOLVED.value
                    before_alert.status = AlertStatus.RESOLVED.value
                    before_alert.origin = "recompute"
                    before_alert.recompute_count = (before_alert.recompute_count or 0) + 1
                    after_snapshot = _alert_snapshot(before_alert)
                    detail_note = "补传后不再满足阈值"
                    counters["resolved"] += 1
            else:
                action = RecomputeAction.SKIPPED.value if outcome.reason == "insufficient_history" else RecomputeAction.UNCHANGED.value
                detail_note = "历史桶不足，不判异常" if outcome.reason == "insufficient_history" else "未命中阈值，本就无告警"
                counters["skipped" if action == RecomputeAction.SKIPPED.value else "unchanged"] += 1

        detail = AlertRecomputeDetail(
            job_id=job.id,
            template_id=template_id,
            bucket_start=target_bucket,
            action=action,
            alert_id=alert_id,
            before_status=before_snapshot["status"] if before_snapshot else None,
            after_status=after_snapshot["status"] if after_snapshot else None,
            before_count=before_snapshot["count"] if before_snapshot else None,
            after_count=after_snapshot["count"] if after_snapshot else None,
            before_z_score=before_snapshot["z_score"] if before_snapshot else None,
            after_z_score=after_snapshot["z_score"] if after_snapshot else None,
            before_error_ratio=before_snapshot["error_ratio"] if before_snapshot else None,
            after_error_ratio=after_snapshot["error_ratio"] if after_snapshot else None,
            reason=outcome.reason,
            note=detail_note,
        )
        db.add(detail)
        details.append(_serialize_detail(detail, template))

    job.created_count = counters["created"]
    job.updated_count = counters["updated"]
    job.resolved_count = counters["resolved"]
    job.unchanged_count = counters["unchanged"]
    job.skipped_count = counters["skipped"]
    job.elapsed_ms = int((time.perf_counter() - started) * 1000)
    job.finished_at = now_local()
    db.flush()
    logger.info(
        "recompute.done job_id=%s pairs=%s created=%s updated=%s resolved=%s unchanged=%s skipped=%s",
        job.id,
        len(pairs),
        counters["created"],
        counters["updated"],
        counters["resolved"],
        counters["unchanged"],
        counters["skipped"],
    )
    return {
        **serialize_job(db, job),
        "deduplicated": False,
        "details": details,
    }


def _serialize_detail(detail: AlertRecomputeDetail, template: LogTemplate | None = None) -> dict:
    return {
        "id": detail.id,
        "job_id": detail.job_id,
        "template_id": detail.template_id,
        "template_str": template.template_str if template else "",
        "service": template.service if template else "",
        "bucket_start": detail.bucket_start.isoformat(sep=" "),
        "action": detail.action,
        "alert_id": detail.alert_id,
        "before_status": detail.before_status,
        "after_status": detail.after_status,
        "before_count": detail.before_count,
        "after_count": detail.after_count,
        "before_z_score": round(detail.before_z_score, 4) if detail.before_z_score is not None else None,
        "after_z_score": round(detail.after_z_score, 4) if detail.after_z_score is not None else None,
        "before_error_ratio": round(detail.before_error_ratio, 4) if detail.before_error_ratio is not None else None,
        "after_error_ratio": round(detail.after_error_ratio, 4) if detail.after_error_ratio is not None else None,
        "reason": detail.reason,
        "note": detail.note,
    }


def serialize_job(db: Session, job: AlertRecomputeJob) -> dict:
    return {
        "id": job.id,
        "idempotency_key": job.idempotency_key,
        "triggered_by": job.triggered_by,
        "range_start": job.range_start.isoformat(sep=" ") if job.range_start else None,
        "range_end": job.range_end.isoformat(sep=" ") if job.range_end else None,
        "affected_bucket_count": job.affected_bucket_count,
        "affected_template_count": job.affected_template_count,
        "pair_count": job.pair_count,
        "created": job.created_count,
        "updated": job.updated_count,
        "resolved": job.resolved_count,
        "unchanged": job.unchanged_count,
        "skipped": job.skipped_count,
        "status": job.status,
        "elapsed_ms": job.elapsed_ms,
        "note": job.note,
        "finished_at": job.finished_at.isoformat(sep=" ") if job.finished_at else None,
    }


def list_recompute_jobs(db: Session, *, limit: int = 20) -> dict:
    limit = max(1, min(limit, 100))
    jobs = (
        db.execute(select(AlertRecomputeJob).order_by(AlertRecomputeJob.id.desc()).limit(limit))
        .scalars()
        .all()
    )
    return {"items": [serialize_job(db, job) for job in jobs], "total": len(jobs)}


def get_recompute_job(db: Session, job_id: int) -> dict:
    job = db.get(AlertRecomputeJob, job_id)
    if job is None:
        raise AppError(codes.NOT_FOUND, "补算批次不存在", f"job_id={job_id}")
    details = (
        db.execute(
            select(AlertRecomputeDetail)
            .where(AlertRecomputeDetail.job_id == job_id)
            .order_by(AlertRecomputeDetail.bucket_start, AlertRecomputeDetail.template_id)
        )
        .scalars()
        .all()
    )
    template_ids = {detail.template_id for detail in details}
    templates = {
        item.id: item
        for item in db.execute(select(LogTemplate).where(LogTemplate.id.in_(list(template_ids) or [0]))).scalars().all()
    }
    payload = serialize_job(db, job)
    payload["details"] = [_serialize_detail(detail, templates.get(detail.template_id)) for detail in details]
    # 按时间桶聚合：告警页按桶查看重算前后的状态与计数
    by_bucket: dict[str, dict] = {}
    for detail in payload["details"]:
        bucket = detail["bucket_start"]
        entry = by_bucket.setdefault(
            bucket,
            {
                "bucket_start": bucket,
                "total": 0,
                "created": 0,
                "updated": 0,
                "resolved": 0,
                "unchanged": 0,
                "skipped": 0,
                "before_firing": 0,
                "after_firing": 0,
            },
        )
        entry["total"] += 1
        entry[detail["action"]] = entry.get(detail["action"], 0) + 1
        if detail["before_status"] in ACTIVE_ALERT_STATUSES:
            entry["before_firing"] += 1
        if detail["after_status"] in ACTIVE_ALERT_STATUSES:
            entry["after_firing"] += 1
    payload["buckets"] = [by_bucket[key] for key in sorted(by_bucket)]
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
