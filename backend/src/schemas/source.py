from __future__ import annotations

from pydantic import BaseModel, Field


class SourceIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    service: str = Field(default="", max_length=80)
    log_format: str = Field(default="plain", pattern="^(plain|json|kv|syslog)$")
    collect_status: str = Field(default="active", pattern="^(active|paused|error)$")
    rate_per_min: int = Field(default=0, ge=0, le=1000000)
    host_group: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=2000)


class SourcePatch(BaseModel):
    log_format: str | None = Field(default=None, pattern="^(plain|json|kv|syslog)$")
    collect_status: str | None = Field(default=None, pattern="^(active|paused|error)$")
    rate_per_min: int | None = Field(default=None, ge=0, le=1000000)
    host_group: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=2000)


class RuleIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    pattern: str = Field(min_length=1, max_length=4000)
    field_names: list[str] = Field(default_factory=list)
    priority: int = Field(default=100, ge=0, le=10000)
    enabled: bool = True


class RulePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    pattern: str | None = Field(default=None, min_length=1, max_length=4000)
    field_names: list[str] | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)
    enabled: bool | None = None
