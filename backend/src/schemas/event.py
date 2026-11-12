from __future__ import annotations

from pydantic import BaseModel


class EventOut(BaseModel):
    id: int
    source_id: int
    source_name: str = ""
    template_id: int | None
    template_str: str = ""
    service: str
    level: str
    raw_line: str
    event_time: str
    bucket_start: str | None
    origin: str


class EventPageOut(BaseModel):
    items: list[EventOut]
    total: int
    page: int
    page_size: int
    pages: int
