"""日志补传后的告警补算（recompute）：只重算受影响的模板 × 时间桶。

两张表：
- AlertRecomputeJob：一次补算批次（触发人、时间范围、受影响桶、汇总计数、幂等键）；
- AlertRecomputeDetail：批次内每个 (模板, 时间桶) 重算前后的状态与判定计数，
  供告警页按时间桶查看「重算前后」差异。

口径：同一 (模板, 时间桶) 的 AlertEvent 只有一条（见 alert_event 唯一约束），
补算对它做幂等 upsert；重复投递同一批日志不会新增告警。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, now_local


class AlertRecomputeJob(Base, TimestampMixin):
    """补算批次：一次手动/自动补算的汇总记录。"""

    __tablename__ = "alert_recompute_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    triggered_by: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    range_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    range_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    affected_bucket_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affected_template_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pair_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="done", index=True)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)


class AlertRecomputeDetail(Base, TimestampMixin):
    """补算明细：一个 (模板, 时间桶) 重算前后的状态与判定快照。"""

    __tablename__ = "alert_recompute_detail"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("alert_recompute_job.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    bucket_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(24), nullable=False, default="unchanged", index=True)
    alert_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    before_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    after_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    before_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    after_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before_z_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    after_z_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    before_error_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    after_error_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")
