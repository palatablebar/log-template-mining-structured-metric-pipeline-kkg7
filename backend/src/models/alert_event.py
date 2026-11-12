from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class AlertEvent(Base, TimestampMixin):
    """告警触发记录：一条 = 一个 (规则, 模板, 桶) 的判定结果（含基线快照便于复盘）。"""

    __tablename__ = "alert_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("alert_rule.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("log_template.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bucket_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    count_in_bucket: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    baseline_median: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    baseline_mad: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    z_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    baseline_error_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="warn")
    reason: Mapped[str] = mapped_column(String(32), nullable=False, default="spike_zscore")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="firing", index=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    acknowledged_by: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    silenced_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    origin: Mapped[str] = mapped_column(String(16), nullable=False, default="scan", index=True)
