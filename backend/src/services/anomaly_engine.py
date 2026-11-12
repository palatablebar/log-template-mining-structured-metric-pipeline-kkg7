"""算法 B：模板级聚合与基线异常检测（纯 Python，不依赖 DB）。

口径（batch-plan gb-555 核心算法 B，逐条对应）：
① 按 (template_id, 5min 桶) 计数，同时统计 error/fatal 行数；
② 基线 = 同模板「当前桶之前」的 12 个桶计数（窗口内没有事件的桶按 0 计）；
③ 稳健 z 分数：z = 0.6745 × (x - median) / MAD；MAD = median(|x_i - median|)，
   MAD == 0 时用 1 兜底（避免除零，同时让「恒定基线 + 突增」仍能判定）；
④ 级别分布骤变：error 占比从基线 < 5% 骤升到当前 > 25%，同样触发；
⑤ 判据：z > 3.5 判尖峰，与 ④ 可同时成立（reason 记为两者）；
   告警去抖：同模板 30 分钟内只保留一条（由 alert_service 依据 silenced_until 执行）。

输出：AlertCandidate（模板 / 桶 / 计数 / 基线中位数 / MAD / z / error 占比 / 触发原因）。
失败态：有效历史桶数 < 3 → 不判异常，标记 insufficient_history 并统计进 skipped。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from src.constants.enums import EventLevel, TriggerReason
from src.utils.time_buckets import BUCKET_MINUTES

BASELINE_BUCKETS = 12
MIN_HISTORY_BUCKETS = 3
Z_THRESHOLD = 3.5
ERROR_RATIO_LOW = 0.05
ERROR_RATIO_HIGH = 0.25
MAD_FALLBACK = 1.0
ERROR_LEVELS = (EventLevel.ERROR.value, EventLevel.FATAL.value)


@dataclass
class BucketStat:
    """一个模板在某个 5min 桶里的计数与级别分布。"""

    bucket_start: datetime
    count: int = 0
    error_count: int = 0
    level_counts: dict[str, int] = field(default_factory=dict)

    @property
    def error_ratio(self) -> float:
        return round(self.error_count / self.count, 4) if self.count else 0.0


@dataclass
class RuleConfig:
    """一条规则的可调参数（来自 alert_rule，允许逐规则覆盖默认口径）。"""

    rule_id: int | None = None
    metric: str = "both"
    baseline_buckets: int = BASELINE_BUCKETS
    z_threshold: float = Z_THRESHOLD
    error_ratio_low: float = ERROR_RATIO_LOW
    error_ratio_high: float = ERROR_RATIO_HIGH
    silence_minutes: int = 30


@dataclass
class AlertCandidate:
    template_id: int
    template_str: str
    service: str
    bucket_start: datetime
    count: int
    baseline_median: float
    baseline_mad: float
    z_score: float
    error_ratio: float
    baseline_error_ratio: float
    reason: str
    level: str
    history_buckets: int

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "template_str": self.template_str,
            "service": self.service,
            "bucket_start": self.bucket_start.isoformat(sep=" "),
            "count": self.count,
            "baseline_median": round(self.baseline_median, 4),
            "baseline_mad": round(self.baseline_mad, 4),
            "z_score": round(self.z_score, 4),
            "error_ratio": round(self.error_ratio, 4),
            "baseline_error_ratio": round(self.baseline_error_ratio, 4),
            "reason": self.reason,
            "level": self.level,
            "history_buckets": self.history_buckets,
        }


@dataclass
class SkippedTemplate:
    template_id: int
    template_str: str
    reason: str
    history_buckets: int

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "template_str": self.template_str,
            "reason": self.reason,
            "history_buckets": self.history_buckets,
        }


@dataclass
class ScanResult:
    bucket: datetime | None
    templates_scanned: int
    alerts: list[AlertCandidate]
    skipped: list[SkippedTemplate]
    elapsed_ms: int = 0

    @property
    def insufficient_history(self) -> int:
        return sum(1 for item in self.skipped if item.reason == "insufficient_history")

    @property
    def within_baseline(self) -> int:
        return sum(1 for item in self.skipped if item.reason == "within_baseline")

    def to_dict(self) -> dict:
        return {
            "bucket": self.bucket.isoformat(sep=" ") if self.bucket else None,
            "templates_scanned": self.templates_scanned,
            "alerts": [item.to_dict() for item in self.alerts],
            "skipped": [item.to_dict() for item in self.skipped],
            "insufficient_history": self.insufficient_history,
            "within_baseline": self.within_baseline,
            "elapsed_ms": self.elapsed_ms,
            "bucket_minutes": BUCKET_MINUTES,
        }


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def mad(values: list[float], center: float) -> float:
    """中位数绝对偏差 MAD = median(|x_i - median|)。"""
    if not values:
        return 0.0
    return median([abs(value - center) for value in values])


def robust_z(x: float, center: float, mad_value: float) -> float:
    """③ z = 0.6745 × (x - median) / MAD；MAD == 0 用 1 兜底。"""
    divisor = mad_value if mad_value > 0 else MAD_FALLBACK
    return 0.6745 * (x - center) / divisor


def build_series(bucket_counts: list[tuple[datetime, int, int]]) -> list[BucketStat]:
    """把 (bucket_start, count, error_count) 转成按时间升序的 BucketStat 列表。"""
    series: list[BucketStat] = []
    for bucket, count, error_count in sorted(bucket_counts, key=lambda item: item[0]):
        series.append(BucketStat(bucket_start=bucket, count=int(count), error_count=int(error_count)))
    return series


def evaluate_template(
    template_id: int,
    template_str: str,
    series: list[BucketStat],
    rule: RuleConfig,
    service: str = "",
) -> AlertCandidate | SkippedTemplate:
    """对一个模板的桶序列做判定：最后一个桶为待检桶，之前 baseline_buckets 个桶为基线。"""
    if len(series) < MIN_HISTORY_BUCKETS + 1:
        return SkippedTemplate(
            template_id=template_id,
            template_str=template_str,
            reason="insufficient_history",
            history_buckets=len(series),
        )

    target = series[-1]
    history = series[-(rule.baseline_buckets + 1): -1]
    if len(history) < MIN_HISTORY_BUCKETS:
        return SkippedTemplate(
            template_id=template_id,
            template_str=template_str,
            reason="insufficient_history",
            history_buckets=len(history),
        )

    history_counts = [float(item.count) for item in history]
    center = median(history_counts)
    mad_value = mad(history_counts, center)
    z_value = robust_z(float(target.count), center, mad_value)

    history_total = sum(item.count for item in history)
    history_errors = sum(item.error_count for item in history)
    baseline_error_ratio = (history_errors / history_total) if history_total else 0.0
    current_error_ratio = target.error_ratio

    spike = z_value > rule.z_threshold and target.count > 0
    ratio_jump = (
        baseline_error_ratio < rule.error_ratio_low
        and current_error_ratio > rule.error_ratio_high
    )

    metric = rule.metric
    if metric == "spike":
        triggered = spike
    elif metric == "error_ratio":
        triggered = ratio_jump
    else:
        triggered = spike or ratio_jump

    if not triggered:
        return SkippedTemplate(
            template_id=template_id,
            template_str=template_str,
            reason="within_baseline",
            history_buckets=len(history),
        )

    if spike and ratio_jump:
        reason = TriggerReason.BOTH.value
    elif spike:
        reason = TriggerReason.SPIKE.value
    else:
        reason = TriggerReason.ERROR_RATIO.value

    level = EventLevel.ERROR.value if (reason != TriggerReason.SPIKE.value and current_error_ratio > rule.error_ratio_high) else EventLevel.WARN.value
    if current_error_ratio >= 0.5:
        level = EventLevel.ERROR.value

    return AlertCandidate(
        template_id=template_id,
        template_str=template_str,
        service=service,
        bucket_start=target.bucket_start,
        count=target.count,
        baseline_median=center,
        baseline_mad=mad_value,
        z_score=z_value,
        error_ratio=current_error_ratio,
        baseline_error_ratio=round(baseline_error_ratio, 4),
        reason=reason,
        level=level,
        history_buckets=len(history),
    )


def scan_series(
    series_by_template: dict[int, tuple[str, str, list[tuple[datetime, int, int]]]],
    rule_for_template,
) -> ScanResult:
    """批量判定：rule_for_template(template_id) -> RuleConfig | None（None 表示该模板无规则）。"""
    alerts: list[AlertCandidate] = []
    skipped: list[SkippedTemplate] = []
    scanned = 0
    latest_bucket: datetime | None = None
    for template_id, (template_str, service, raw_series) in series_by_template.items():
        rule = rule_for_template(template_id)
        if rule is None:
            continue
        series = build_series(raw_series)
        if not series:
            continue
        scanned += 1
        if latest_bucket is None or series[-1].bucket_start > latest_bucket:
            latest_bucket = series[-1].bucket_start
        outcome = evaluate_template(template_id, template_str, series, rule, service)
        if isinstance(outcome, AlertCandidate):
            alerts.append(outcome)
        else:
            skipped.append(outcome)
    alerts.sort(key=lambda item: (-item.z_score, item.template_id))
    return ScanResult(bucket=latest_bucket, templates_scanned=scanned, alerts=alerts, skipped=skipped)


def describe_formula() -> dict:
    """把口径作为可展示元数据返回（前端「公式说明」卡片与 README 共用）。"""
    return {
        "bucket_minutes": BUCKET_MINUTES,
        "baseline_buckets": BASELINE_BUCKETS,
        "min_history_buckets": MIN_HISTORY_BUCKETS,
        "z_threshold": Z_THRESHOLD,
        "mad_fallback": MAD_FALLBACK,
        "error_ratio_low": ERROR_RATIO_LOW,
        "error_ratio_high": ERROR_RATIO_HIGH,
        "z_formula": "z = 0.6745 * (x - median) / MAD",
        "spike_rule": "z > 3.5",
        "ratio_rule": "baseline_error_ratio < 5% 且 current_error_ratio > 25%",
        "silence_minutes": 30,
    }


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number

__all__ = [
    "AlertCandidate",
    "BucketStat",
    "RuleConfig",
    "ScanResult",
    "SkippedTemplate",
    "build_series",
    "describe_formula",
    "evaluate_template",
    "mad",
    "median",
    "robust_z",
    "scan_series",
    "BASELINE_BUCKETS",
    "MIN_HISTORY_BUCKETS",
    "Z_THRESHOLD",
]
