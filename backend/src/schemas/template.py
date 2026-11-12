from __future__ import annotations

from pydantic import BaseModel


class TemplateOut(BaseModel):
    id: int
    signature: str
    template_str: str
    token_count: int
    slot_types: list[str]
    slot_names: list[str]
    source_id: int | None
    source_name: str = ""
    service: str
    status: str
    is_noise: bool
    frequency: int
    level_hint: str
    slot_count: int = 0
    origin: str = "seed"


class TemplateDetailOut(TemplateOut):
    sample_line: str = ""
    samples: list[dict] = []
