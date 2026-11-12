"""通用响应模型。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MessageOut(BaseModel):
    message: str
    detail: dict[str, Any] | None = None


class ErrorOut(BaseModel):
    code: str
    message: str
    detail: str = ""
    trace_id: str | None = None
