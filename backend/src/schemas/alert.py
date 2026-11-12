from __future__ import annotations

from pydantic import BaseModel, Field


class AlertRuleIn(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    template_id: int | None = None
    metric: str = Field(default="both", pattern="^(spike|error_ratio|both)$")
    window_minutes: int = Field(default=5, ge=1, le=60)
    baseline_buckets: int = Field(default=12, ge=3, le=288)
    z_threshold: float = Field(default=3.5, ge=0.5, le=20)
    error_ratio_low: float = Field(default=0.05, ge=0, le=1)
    error_ratio_high: float = Field(default=0.25, ge=0, le=1)
    silence_minutes: int = Field(default=30, ge=1, le=1440)
    enabled: bool = True
    description: str = Field(default="", max_length=1000)


class AlertRulePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=140)
    metric: str | None = Field(default=None, pattern="^(spike|error_ratio|both)$")
    baseline_buckets: int | None = Field(default=None, ge=3, le=288)
    z_threshold: float | None = Field(default=None, ge=0.5, le=20)
    error_ratio_low: float | None = Field(default=None, ge=0, le=1)
    error_ratio_high: float | None = Field(default=None, ge=0, le=1)
    silence_minutes: int | None = Field(default=None, ge=1, le=1440)
    enabled: bool | None = None
    description: str | None = Field(default=None, max_length=1000)


class AckIn(BaseModel):
    note: str = Field(default="", max_length=1000)
    silence_minutes: int | None = Field(default=None, ge=1, le=1440)


class SilenceIn(BaseModel):
    minutes: int = Field(default=30, ge=1, le=1440)
    note: str = Field(default="", max_length=1000)
