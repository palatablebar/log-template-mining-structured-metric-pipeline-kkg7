from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class LogEvent(Base, TimestampMixin):
    """日志事件：一行原始日志。自然键 = line_hash（导入去重）。"""

    __tablename__ = "log_event"
    __table_args__ = (
        Index("ix_event_template_time", "template_id", "event_time"),
        Index("ix_event_time", "event_time"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("log_source.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("log_template.id", ondelete="SET NULL"), nullable=True, index=True
    )
    raw_line: Mapped[str] = mapped_column(Text, nullable=False)
    line_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    fields: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info", index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    bucket_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    origin: Mapped[str] = mapped_column(String(16), nullable=False, default="seed", index=True)
    service: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    ingest_batch: Mapped[str] = mapped_column(String(64), nullable=False, default="")
