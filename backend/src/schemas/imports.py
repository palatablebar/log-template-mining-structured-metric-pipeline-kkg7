from __future__ import annotations

from pydantic import BaseModel, Field


class MineIn(BaseModel):
    text: str = Field(min_length=1, description="上传的日志样本全文")
    apply: bool = Field(default=False, description="true 时直接应用（落模板 + 回填事件）")


class ApplyIn(BaseModel):
    text: str = Field(min_length=1)


class MineTemplateOut(BaseModel):
    template_str: str
    token_count: int
    slot_types: list[str]
    slot_names: list[str]
    sample_count: int
    sample_line: str
    signature: str
    status: str
    level_hint: str
    is_new: bool = True
    suggested_source_id: int | None = None
    suggested_source_name: str = ""
