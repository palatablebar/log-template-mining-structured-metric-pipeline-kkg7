"""模板库：列表 / 详情 / 确认 / 噪声标记。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import TemplateStatus
from src.models.base import now_local
from src.models.log_event import LogEvent
from src.models.log_source import LogSource
from src.models.log_template import LogTemplate
from src.utils.errors import AppError


def serialize_template(template: LogTemplate, source_name: str = "", event_count: int | None = None) -> dict:
    return {
        "id": template.id,
        "signature": template.signature,
        "template_str": template.template_str,
        "token_count": template.token_count,
        "slot_types": list(template.slot_types or []),
        "slot_names": list(template.slot_names or []),
        "source_id": template.source_id,
        "source_name": source_name,
        "service": template.service,
        "sample_line": template.sample_line,
        "level_hint": template.level_hint,
        "status": template.status,
        "is_noise": bool(template.is_noise),
        "frequency": template.frequency,
        "event_count": event_count if event_count is not None else template.frequency,
        "first_seen_at": template.first_seen_at.isoformat(sep=" ") if template.first_seen_at else None,
        "last_seen_at": template.last_seen_at.isoformat(sep=" ") if template.last_seen_at else None,
        "origin": template.origin,
        "slot_count": sum(1 for item in (template.slot_types or []) if item not in ("static", "")),
    }


def list_templates(
    db: Session,
    *,
    status: str | None = None,
    source_id: int | None = None,
    search: str | None = None,
    include_noise: bool = False,
    limit: int = 200,
) -> list[dict]:
    query = select(LogTemplate).order_by(LogTemplate.frequency.desc(), LogTemplate.id)
    if status:
        query = query.where(LogTemplate.status == status)
    if source_id is not None:
        query = query.where(LogTemplate.source_id == source_id)
    if search:
        query = query.where(LogTemplate.template_str.like(f"%{search}%"))
    if not include_noise:
        query = query.where(LogTemplate.is_noise.is_(False))
    templates = db.execute(query.limit(limit)).scalars().all()
    source_names = dict(db.execute(select(LogSource.id, LogSource.name)).all())
    return [serialize_template(item, source_names.get(item.source_id, "")) for item in templates]


def get_template(db: Session, template_id: int) -> dict:
    template = db.get(LogTemplate, template_id)
    if template is None:
        raise AppError(codes.TEMPLATE_NOT_FOUND, "模板不存在", f"template_id={template_id}")
    source = db.get(LogSource, template.source_id) if template.source_id else None
    samples = (
        db.execute(
            select(LogEvent.raw_line, LogEvent.level, LogEvent.event_time)
            .where(LogEvent.template_id == template_id)
            .order_by(LogEvent.event_time.desc())
            .limit(5)
        )
        .all()
    )
    payload = serialize_template(template, source.name if source else "")
    payload["samples"] = [
        {"raw_line": row[0], "level": row[1], "event_time": row[2].isoformat(sep=" ")} for row in samples
    ]
    return payload


def confirm_template(db: Session, template_id: int, actor: str) -> dict:
    template = db.get(LogTemplate, template_id)
    if template is None:
        raise AppError(codes.TEMPLATE_NOT_FOUND, "模板不存在", f"template_id={template_id}")
    template.status = TemplateStatus.CONFIRMED.value
    template.confirmed_by = actor
    template.updated_at = now_local()
    db.flush()
    return serialize_template(template)


def mark_noise(db: Session, template_id: int, actor: str) -> dict:
    template = db.get(LogTemplate, template_id)
    if template is None:
        raise AppError(codes.TEMPLATE_NOT_FOUND, "模板不存在", f"template_id={template_id}")
    template.status = TemplateStatus.NOISE.value
    template.is_noise = True
    template.confirmed_by = actor
    template.updated_at = now_local()
    db.flush()
    return serialize_template(template)


def overview(db: Session) -> dict:
    total = db.execute(select(func.count()).select_from(LogTemplate)).scalar_one()
    noise = db.execute(
        select(func.count()).select_from(LogTemplate).where(LogTemplate.is_noise.is_(True))
    ).scalar_one()
    tentative = db.execute(
        select(func.count()).select_from(LogTemplate).where(LogTemplate.status == TemplateStatus.TENTATIVE.value)
    ).scalar_one()
    slot_total = 0
    for template in db.execute(select(LogTemplate.slot_types)).scalars().all():
        slot_total += sum(1 for item in (template or []) if item not in ("static", ""))
    return {"templates": int(total) - int(noise), "noise": int(noise), "tentative": int(tentative), "slots": slot_total}
