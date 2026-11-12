"""Declarative base：MySQL 8.0，统一 utf8mb4，时间用本地 naive datetime。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

metadata_obj = MetaData()


def now_local() -> datetime:
    """本地时间（Asia/Shanghai，容器 TZ 固定）。DB 列不带时区。"""
    return datetime.now().replace(microsecond=0)


class Base(DeclarativeBase):
    metadata = metadata_obj


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, nullable=False)
