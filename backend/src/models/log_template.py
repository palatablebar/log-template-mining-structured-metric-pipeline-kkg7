from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, now_local


class LogTemplate(Base, TimestampMixin):
    """日志模板：模板串（token 用空格分隔，变量位 = <*>）。自然键 = signature。"""

    __tablename__ = "log_template"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    signature: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    template_str: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    slot_types: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    slot_names: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("log_source.id", ondelete="SET NULL"), nullable=True, index=True
    )
    service: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    sample_line: Mapped[str] = mapped_column(Text, nullable=False, default="")
    level_hint: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="mined", index=True)
    is_noise: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    origin: Mapped[str] = mapped_column(String(16), nullable=False, default="seed", index=True)
    confirmed_by: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local, nullable=False)
