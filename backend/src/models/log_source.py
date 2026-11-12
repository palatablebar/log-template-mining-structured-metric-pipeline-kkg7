from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, now_local


class LogSource(Base, TimestampMixin):
    """日志源：一个服务 × 一种采集格式。自然键 = name。"""

    __tablename__ = "log_source"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    service: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    log_format: Mapped[str] = mapped_column(String(20), nullable=False, default="plain")
    collect_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    rate_per_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    host_group: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local, nullable=False)
