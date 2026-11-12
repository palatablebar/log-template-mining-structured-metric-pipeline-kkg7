"""事件检索 / 趋势 / 聚合。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from src.services import event_service
from src.utils.time_buckets import parse_log_time


def _parse_time(text: str | None) -> datetime | None:
    if not text:
        return None
    return parse_log_time(text)


def search(
    db: Session,
    *,
    template_id: int | None = None,
    source_id: int | None = None,
    level: str | None = None,
    search: str | None = None,
    pending_only: bool = False,
    start: str | None = None,
    end: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    return event_service.search_events(
        db,
        template_id=template_id,
        source_id=source_id,
        level=level,
        search=search,
        pending_only=pending_only,
        start=_parse_time(start),
        end=_parse_time(end),
        page=page,
        page_size=page_size,
    )


def trend(db: Session, *, buckets: int = 36, template_id: int | None = None) -> dict:
    return event_service.trend(db, buckets=buckets, template_id=template_id)


def aggregate(db: Session, *, top: int = 12) -> dict:
    items = event_service.aggregate_by_template(db, top=top)
    return {"items": items, "total": len(items)}


def levels(db: Session, *, template_id: int | None = None) -> dict:
    return {"items": event_service.level_distribution(db, template_id=template_id)}
