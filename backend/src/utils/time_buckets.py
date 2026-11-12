"""时间桶工具：5 分钟对齐、桶区间枚举、事件时间解析。

事件时间统一用「naive 本地时间（Asia/Shanghai）」存储，MySQL DATETIME 不带时区，
避免 UTC/本地混存导致桶边界抖动。
"""
from __future__ import annotations

from datetime import datetime, timedelta

BUCKET_MINUTES = 5


def bucket_start(moment: datetime, bucket_minutes: int = BUCKET_MINUTES) -> datetime:
    """把时刻对齐到桶起点（默认 5 分钟）。"""
    minute = (moment.minute // bucket_minutes) * bucket_minutes
    return moment.replace(minute=minute, second=0, microsecond=0)


def bucket_end(start: datetime, bucket_minutes: int = BUCKET_MINUTES) -> datetime:
    return start + timedelta(minutes=bucket_minutes)


def iter_buckets(start: datetime, end: datetime, bucket_minutes: int = BUCKET_MINUTES) -> list[datetime]:
    """[start, end) 内所有桶起点（含 start，不含 end）。"""
    current = bucket_start(start, bucket_minutes)
    limit = bucket_start(end, bucket_minutes)
    buckets: list[datetime] = []
    while current <= limit:
        buckets.append(current)
        current += timedelta(minutes=bucket_minutes)
    return buckets


def last_n_buckets(anchor: datetime, count: int, bucket_minutes: int = BUCKET_MINUTES) -> list[datetime]:
    """以 anchor 所在桶为最后一桶，向前取 count 个桶起点（升序）。"""
    end = bucket_start(anchor, bucket_minutes)
    start = end - timedelta(minutes=bucket_minutes * (count - 1))
    return iter_buckets(start, end, bucket_minutes)


LOG_TIME_FORMATS: tuple[str, ...] = (
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)


def parse_log_time(text: str) -> datetime | None:
    """解析日志行首时间戳（支持 ISO/空格分隔、毫秒可选、尾部 Z）。"""
    candidate = text.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1]
    for fmt in LOG_TIME_FORMATS:
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    return None


def parse_anchor(text: str) -> datetime:
    parsed = parse_log_time(text)
    if parsed is None:
        raise ValueError(f"无法解析 SEED_ANCHOR: {text}")
    return parsed
