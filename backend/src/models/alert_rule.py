from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, now_local


class AlertRule(Base, TimestampMixin):
    """告警规则：模板级（template_id 有值）或全局（NULL 表示所有模板）。自然键 = name。"""

    __tablename__ = "alert_rule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)
    template_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("log_template.id", ondelete="SET NULL"), nullable=True, index=True
    )
    metric: Mapped[str] = mapped_column(String(24), nullable=False, default="spike")
    window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    baseline_buckets: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    z_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=3.5)
    error_ratio_low: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    error_ratio_high: Mapped[float] = mapped_column(Float, nullable=False, default=0.25)
    silence_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local, nullable=False)
