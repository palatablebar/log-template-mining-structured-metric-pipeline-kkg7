"""事件检索与按模板聚合趋势。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import EventLevel
from src.constants.limits import DEFAULT_EVENT_PAGE_SIZE, MAX_EVENT_PAGE_SIZE, MAX_TREND_BUCKETS
from src.models.log_event import LogEvent
from src.models.log_source import LogSource
from src.models.log_template import LogTemplate
from src.utils.errors import AppError
from src.utils.time_buckets import BUCKET_MINUTES, bucket_start, last_n_buckets


def _serialize_event(db: Session, event: LogEvent, source_name: str, template_str: str) -> dict:
    return {
        "id": event.id,
        "source_id": event.source_id,
        "source_name": source_name,
        "template_id": event.template_id,
        "template_str": template_str,
        "service": event.service,
        "level": event.level,
        "raw_line": event.raw_line,
        "fields": dict(event.fields or {}),
        "event_time": event.event_time.isoformat(sep=" "),
        "bucket_start": event.bucket_start.isoformat(sep=" ") if event.bucket_start else None,
        "origin": event.origin,
    }


def search_events(
    db: Session,
    *,
    template_id: int | None = None,
    source_id: int | None = None,
    level: str | None = None,
    search: str | None = None,
    pending_only: bool = False,
    start: datetime | None = None,
    end: datetime | None = None,
    page: int = 1,
    page_size: int = DEFAULT_EVENT_PAGE_SIZE,
) -> dict:
    if page_size < 1 or page_size > MAX_EVENT_PAGE_SIZE:
        raise AppError(codes.EVENT_QUERY_INVALID, f"page_size 必须在 1..{MAX_EVENT_PAGE_SIZE}", str(page_size))
    if page < 1:
        raise AppError(codes.EVENT_QUERY_INVALID, "page 必须 >= 1", str(page))
    if level and level not in tuple(item.value for item in EventLevel):
        raise AppError(codes.EVENT_QUERY_INVALID, f"level 非法: {level}", str(level))

    conditions = []
    if template_id is not None:
        conditions.append(LogEvent.template_id == template_id)
    if source_id is not None:
        conditions.append(LogEvent.source_id == source_id)
    if level:
        conditions.append(LogEvent.level == level)
    if search:
        conditions.append(LogEvent.raw_line.like(f"%{search}%"))
    if pending_only:
        conditions.append(LogEvent.template_id.is_(None))
    if start is not None:
        conditions.append(LogEvent.event_time >= start)
    if end is not None:
        conditions.append(LogEvent.event_time <= end)

    base = select(LogEvent)
    count_query = select(func.count()).select_from(LogEvent)
    for condition in conditions:
        base = base.where(condition)
        count_query = count_query.where(condition)

    total = int(db.execute(count_query).scalar_one())
    rows = (
        db.execute(
            base.order_by(LogEvent.event_time.desc(), LogEvent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    source_names = dict(db.execute(select(LogSource.id, LogSource.name)).all())
    template_strs = dict(db.execute(select(LogTemplate.id, LogTemplate.template_str)).all())
    items = [
        _serialize_event(db, row, source_names.get(row.source_id, ""), template_strs.get(row.template_id or -1, ""))
        for row in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


def aggregate_by_template(db: Session, *, top: int = 12) -> list[dict]:
    """按模板聚合（窗口内总量 + error 占比），给 /events 的排行条用。"""
    rows = db.execute(
        select(
            LogTemplate.id,
            LogTemplate.template_str,
            LogTemplate.service,
            func.count(LogEvent.id).label("total"),
            func.sum(
                case((LogEvent.level.in_(("error", "fatal")), 1), else_=0)
            ).label("errors"),
        )
        .join(LogEvent, LogEvent.template_id == LogTemplate.id)
        .where(LogTemplate.is_noise.is_(False))
        .group_by(LogTemplate.id, LogTemplate.template_str, LogTemplate.service)
        .order_by(func.count(LogEvent.id).desc())
        .limit(top)
    ).all()
    return [
        {
            "template_id": row[0],
            "template_str": row[1],
            "service": row[2],
            "event_count": int(row[3] or 0),
            "error_count": int(row[4] or 0),
            "error_ratio": round((row[4] or 0) / row[3], 4) if row[3] else 0.0,
        }
        for row in rows
    ]


def trend(
    db: Session,
    *,
    buckets: int = 36,
    template_id: int | None = None,
) -> dict:
    """按 (template, 5min 桶) 分组计数 → 趋势序列；缺桶补 0（对齐到全局最新桶）。"""
    buckets = max(4, min(buckets, MAX_TREND_BUCKETS))
    anchor_row = db.execute(select(func.max(LogEvent.bucket_start))).scalar_one_or_none()
    if anchor_row is None:
        return {"anchor": None, "bucket_minutes": BUCKET_MINUTES, "series": [], "buckets": []}
    anchor = bucket_start(anchor_row)
    bucket_list = last_n_buckets(anchor, buckets)
    window_start = bucket_list[0]

    conditions = [LogEvent.bucket_start.is_not(None), LogEvent.bucket_start >= window_start]
    if template_id is not None:
        conditions.append(LogEvent.template_id == template_id)
    else:
        conditions.append(LogEvent.template_id.is_not(None))

    rows = db.execute(
        select(
            LogEvent.template_id,
            LogEvent.bucket_start,
            func.count(LogEvent.id),
            func.sum(case((LogEvent.level.in_(("error", "fatal")), 1), else_=0)),
        )
        .where(*conditions)
        .group_by(LogEvent.template_id, LogEvent.bucket_start)
    ).all()

    template_strs = dict(db.execute(select(LogTemplate.id, LogTemplate.template_str)).all())
    services = dict(db.execute(select(LogTemplate.id, LogTemplate.service)).all())
    by_template: dict[int, dict] = {}
    for template_id_, bucket_at, count, errors in rows:
        entry = by_template.setdefault(
            int(template_id_),
            {
                "template_id": int(template_id_),
                "template_str": template_strs.get(int(template_id_), ""),
                "service": services.get(int(template_id_), ""),
                "counts": {item: 0 for item in bucket_list},
                "errors": {item: 0 for item in bucket_list},
            },
        )
        entry["counts"][bucket_at] = int(count or 0)
        entry["errors"][bucket_at] = int(errors or 0)

    series = sorted(
        by_template.values(),
        key=lambda item: (
            -sum(item["errors"].values()),
            -max(item["counts"].values()) if item["counts"] else 0,
            -sum(item["counts"].values()),
        ),
    )
    for entry in series:
        entry["total"] = sum(entry["counts"].values())
        entry["peak"] = max(entry["counts"].values()) if entry["counts"] else 0
        entry["series"] = [entry["counts"][item] for item in bucket_list]
        entry["error_series"] = [entry["errors"][item] for item in bucket_list]

    return {
        "anchor": anchor.isoformat(sep=" "),
        "bucket_minutes": BUCKET_MINUTES,
        "buckets": [item.isoformat(sep=" ") for item in bucket_list],
        "series": series,
    }


def level_distribution(db: Session, *, template_id: int | None = None) -> list[dict]:
    conditions = []
    if template_id is not None:
        conditions.append(LogEvent.template_id == template_id)
    rows = db.execute(select(LogEvent.level, func.count()).where(*conditions).group_by(LogEvent.level)).all()
    total = sum(int(row[1]) for row in rows) or 1
    return [
        {"level": row[0], "count": int(row[1]), "ratio": round(int(row[1]) / total, 4)} for row in rows
    ]
