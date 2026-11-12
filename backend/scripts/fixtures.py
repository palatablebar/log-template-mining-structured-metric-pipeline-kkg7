"""演示日志样本生成器（确定性，无随机模块）。

同一份生成器同时服务三处，保证「seed 里 pending 的 240 行」与「/import 上传的样本」
逐字一致，导入时可按 line_hash 去重：
1. `scripts/seed_demo.py`：8 个已挖掘模板的 6000 行 + 240 行待归类新格式 + 9 行噪声；
2. `GET /api/imports/sample`：返回 249 行样本文件（240 新格式 + 9 噪声）；
3. 端到端测试脚本：把样本落盘再上传。

时间轴：以 SEED_ANCHOR（默认 2026-11-10T15:05:00）为「当前桶」起点，桶宽 5 分钟。
事件时间 = 桶起点 + 桶内偏移秒，固定可复现，异常检测的 z 值才可验收。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.utils.time_buckets import BUCKET_MINUTES, bucket_start

SERVICES = ("order-svc", "gateway-svc", "auth-svc", "pay-svc")


def _stable_int(seed: str, low: int, high: int) -> int:
    """确定性取值：[low, high] 之间（用 sha256 摘要，不依赖 random）。"""
    if high <= low:
        return low
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    span = high - low + 1
    return low + int(digest[:12], 16) % span


def _hex_id(seed: str, length: int = 8) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return digest[:length]


@dataclass(frozen=True)
class FormatSpec:
    """一种日志行格式：模板 + 变量取值生成 + 桶内计数曲线。"""

    key: str
    service: str
    template: str
    level_pattern: str  # 正常行的级别
    slug: str


# ---------------------------------------------------------------- 8 个已挖掘格式
SEEDED_FORMATS: tuple[FormatSpec, ...] = (
    FormatSpec(
        key="order_routed",
        service="order-svc",
        template=(
            "{ts} INFO order-svc order routed order_id=ORD-{oid} items={items} "
            "total={amount} channel=app"
        ),
        level_pattern="info",
        slug="order routed",
    ),
    FormatSpec(
        key="order_cancelled",
        service="order-svc",
        template=(
            "{ts} WARN order-svc order cancelled order_id=ORD-{oid} reason=customer_request "
            "refund={amount} channel=app retry=0"
        ),
        level_pattern="warn",
        slug="order cancelled",
    ),
    FormatSpec(
        key="gateway_timeout",
        service="gateway-svc",
        template=(
            "{ts} {level} gateway-svc upstream timeout target=inventory-api elapsed_ms={elapsed} "
            "attempt={attempt} route=/api/v1/stock trace={trace} region=cn-east"
        ),
        level_pattern="warn",
        slug="upstream timeout",
    ),
    FormatSpec(
        key="gateway_completed",
        service="gateway-svc",
        template=(
            "{ts} INFO gateway-svc request completed id=req-{rid} method=GET path=/api/v1/{path} "
            "status={status} elapsed_ms={elapsed} client={ip} region=cn-east cache=hit"
        ),
        level_pattern="info",
        slug="request completed",
    ),
    FormatSpec(
        key="auth_refresh",
        service="auth-svc",
        template=(
            "{ts} {level} auth-svc token refresh user=u-{uid} uid={uid} ip={ip} "
            "session=sess-{sid} ttl=1800 clock_skew_ms={skew} region=cn-east"
        ),
        level_pattern="warn",
        slug="token refresh",
    ),
    FormatSpec(
        key="auth_login",
        service="auth-svc",
        template=(
            "{ts} INFO auth-svc login succeeded user=u-{uid} uid={uid} ip={ip} ua={ua} "
            "method=password session=sess-{sid} ttl=1800 mfa=none device=web region=cn-east"
        ),
        level_pattern="info",
        slug="login succeeded",
    ),
    FormatSpec(
        key="pay_settlement",
        service="pay-svc",
        template=(
            "{ts} INFO pay-svc settlement posted batch=B-{bid} merchant=M-{mid} txn_count={items} "
            "amount={amount} currency=CNY settle_date=2026-11-10 status=posted operator=sre-bot "
            "ledger=ledger-{lid} reconciler=v3 region=cn-east"
        ),
        level_pattern="info",
        slug="settlement posted",
    ),
    FormatSpec(
        key="pay_charge",
        service="pay-svc",
        template=(
            "{ts} INFO pay-svc charge accepted order_id=ORD-{oid} txn={trace} amount={amount} "
            "currency=CNY channel=alipay code=0 latency_ms={elapsed} merchant=M-{mid} "
            "terminal=POS-{tid} fee={fee} settled=false region=cn-east"
        ),
        level_pattern="info",
        slug="charge accepted",
    ),
)

# ---------------------------------------------------------------- 3 种新格式（5 个形态）
NEW_FORMATS: tuple[FormatSpec, ...] = (
    FormatSpec(
        key="order_v2_dispatch",
        service="order-svc.v2",
        template=(
            "{ts} INFO order-svc.v2 handler=dispatch order=ORD-{oid} "
            "duration_ms={elapsed} queue=priority-a node={host} attempt=1 trace={trace} "
            'msg="order dispatched to warehouse"'
        ),
        level_pattern="info",
        slug="order dispatched",
    ),
    FormatSpec(
        key="order_v2_retry",
        service="order-svc.v2",
        template=(
            "{ts} {level} order-svc.v2 handler=retry order=ORD-{oid} attempt={attempt} "
            "backoff_ms={elapsed} queue=priority-a node={host} reason=downstream_5xx "
            "trace={trace} retryable=true origin=order-api tenant=t-{mid} shard={items} "
            "idempotent=true budget_ms={elapsed} region=cn-east-2 sla=gold"
        ),
        level_pattern="warn",
        slug="retry scheduled",
    ),
    FormatSpec(
        key="gateway_v2_route",
        service="gateway-svc.v2",
        template=(
            "{ts} INFO gateway-svc.v2 route matched rule=r-{rid} upstream=order-svc "
            "path=/api/v2/order weight={items} zone=cn-east-2 canary={flag} picked=order-svc "
            "cache=miss client={ip} subnet=cn-east-2a tls=TLSv1.3 sni=api.logmine.demo "
            "keepalive=true retries=0 timeout_ms=800"
        ),
        level_pattern="info",
        slug="route matched",
    ),
    FormatSpec(
        key="gateway_v2_breaker",
        service="gateway-svc.v2",
        template=(
            "{ts} WARN gateway-svc.v2 circuit breaker open upstream=pay-svc failures={items} "
            "threshold=20 window_s=60 zone=cn-east-2 recovery=scheduled opened_by=probe "
            "cooldown_s=30 probe=active state=open breaker_id=cb-{rid} fallback=stale "
            "metrics_window=60 opened_at=2026-11-10T15:00:00Z notify=oncall owner=sre-2 state_window=60"
        ),
        level_pattern="warn",
        slug="circuit breaker open",
    ),
    FormatSpec(
        key="pay_v2_settlement",
        service="pay-svc.v2",
        template=(
            "{ts} INFO pay-svc.v2 settlement posted batch=B-{bid} merchant=M-{mid} "
            "txn_count={items} amount={amount} currency=CNY ledger=ledger-{lid} "
            "reconciler=v3 zone=cn-east-2 checksum={trace} acquirer=cmb-settle "
            "processor=paycore-v3 batch_seq={items} submitted_at=2026-11-10T15:00:00Z "
            "currency_scale=2 ledger_close=open recon_id=rc-{rid} audit=on"
        ),
        level_pattern="info",
        slug="settlement posted",
    ),
)

NOISE_LINES: tuple[str, ...] = (
    "",
    "",
    "------------------------------------------------------------",
    "............................................................",
    "",
    "============================================================",
    "....",
    "",
    "#####",
)

# 事件数：6000（8 模板 × 750）+ 240 待归类 = 6240
EVENTS_PER_SEEDED_TEMPLATE = 750
PENDING_LINES_TOTAL = 240

# 当前桶（anchored at SEED_ANCHOR）之前的 12 个桶的计数曲线
SPIKE_TEMPLATE_KEY = "gateway_timeout"
ERROR_RATIO_TEMPLATE_KEY = "auth_refresh"
SPIKE_PATTERN = (3, 3, 3, 3, 3, 3, 2, 4, 2, 4, 2, 4)   # 中位数 3，MAD 0.5 → 当前桶 8 行 z=6.745
FLAT_PATTERN = (5, 5, 6, 4, 5, 6, 5, 4, 5, 6, 5, 4)     # 中位数 5，MAD 0.5 → 当前桶 5 行 z=0
SPIKE_CURRENT_COUNT = 8
FLAT_CURRENT_COUNT = 5
ERROR_RATIO_CURRENT_COUNT = 5
ERROR_RATIO_CURRENT_ERRORS = 2

# 新格式（待归类）240 行：5 个形态的桶内分布，retry 形态在最新桶有 8 行 error
NEW_TEMPLATE_BUCKET_PLANS: dict[str, dict] = {
    "order_v2_dispatch": {"total": 60, "pattern": (5, 5, 5, 4, 5, 5, 5, 4, 5, 5, 5, 5), "current": 2, "current_errors": 0},
    "order_v2_retry": {"total": 44, "pattern": SPIKE_PATTERN, "current": SPIKE_CURRENT_COUNT, "current_errors": 8},
    "gateway_v2_route": {"total": 60, "pattern": (5, 5, 5, 4, 5, 5, 5, 4, 5, 5, 5, 5), "current": 2, "current_errors": 0},
    "gateway_v2_breaker": {"total": 40, "pattern": (3, 3, 3, 4, 3, 3, 4, 3, 3, 4, 3, 4), "current": 0, "current_errors": 0},
    "pay_v2_settlement": {"total": 36, "pattern": (3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3), "current": 0, "current_errors": 0},
}


def anchor_datetime(anchor_text: str) -> datetime:
    from src.utils.time_buckets import parse_anchor

    return parse_anchor(anchor_text)


def current_bucket(anchor_text: str) -> datetime:
    return bucket_start(anchor_datetime(anchor_text))


def _value_fields(spec: FormatSpec, index: int) -> dict[str, str]:
    seed = f"{spec.key}:{index}"
    oid = str(_stable_int(seed + ":oid", 10000, 99999))
    return {
        "oid": oid,
        "items": str(_stable_int(seed + ":items", 1, 12)),
        "amount": f"{_stable_int(seed + ':amount', 1000, 99999) / 100:.2f}",
        "elapsed": str(_stable_int(seed + ":elapsed", 40, 4800)),
        "attempt": str(_stable_int(seed + ":attempt", 1, 3)),
        "trace": _hex_id(seed + ":trace", 8),
        "rid": _hex_id(seed + ":rid", 6),
        "path": ("stock", "order", "cart", "price")[_stable_int(seed + ":path", 0, 3)],
        "status": str((200, 200, 200, 201, 204, 304, 500)[_stable_int(seed + ":status", 0, 6)]),
        "ip": f"10.{_stable_int(seed + ':ip2', 0, 255)}.{_stable_int(seed + ':ip3', 0, 255)}.{_stable_int(seed + ':ip4', 1, 254)}",
        "uid": str(_stable_int(seed + ":uid", 1000, 9999)),
        "ua": ("Mozilla/5.0", "okhttp/4.12", "python-requests/2.32")[_stable_int(seed + ":ua", 0, 2)],
        "sid": _hex_id(seed + ":sid", 6),
        "skew": str(_stable_int(seed + ":skew", -180, 240)),
        "bid": str(_stable_int(seed + ":bid", 8100, 8999)),
        "mid": str(_stable_int(seed + ":mid", 100, 999)),
        "lid": _hex_id(seed + ":lid", 5),
        "tid": str(_stable_int(seed + ":tid", 100, 999)),
        "fee": f"{_stable_int(seed + ':fee', 10, 500) / 100:.2f}",
        "host": f"ip-10-2-{_stable_int(seed + ':host', 1, 30)}-{_stable_int(seed + ':host2', 10, 99)}",
        "flag": "true" if _stable_int(seed + ":flag", 0, 9) < 6 else "false",
    }


def render_line(spec: FormatSpec, index: int, moment: datetime, level: str) -> str:
    ts = moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}"
    payload = _value_fields(spec, index)
    payload["ts"] = ts
    payload["level"] = level.upper()
    return spec.template.format(**payload)


def _bucket_counts(total: int, pattern: tuple[int, ...], current: int) -> list[int]:
    """返回 13 个桶计数：[当前桶] + 前 12 桶；余额摊到更早的桶里（不进基线窗口）。"""
    prior = list(pattern)
    assigned = current + sum(prior)
    older = total - assigned
    if older < 0:
        raise ValueError(f"bucket plan overflows: total={total} assigned={assigned}")
    return [current] + prior, older


def _distribute_older(older: int, bucket_count: int) -> list[int]:
    if bucket_count <= 0 or older <= 0:
        return [0] * max(0, bucket_count)
    base = older // bucket_count
    remainder = older % bucket_count
    return [base + (1 if index < remainder else 0) for index in range(bucket_count)]


@dataclass(frozen=True)
class GeneratedEvent:
    """一条生成的日志行（含模板归属提示和时间）。"""

    raw_line: str
    event_time: datetime
    level: str
    service: str
    format_key: str
    source_name: str


def _source_name_for(spec: FormatSpec) -> str:
    return f"{spec.service}-filebeat"


def _emit(spec: FormatSpec, index: int, bucket_start_at: datetime, within_bucket: int, level: str) -> GeneratedEvent:
    offset_seconds = within_bucket % 300
    moment = bucket_start_at + timedelta(seconds=offset_seconds, milliseconds=(index * 37) % 1000)
    # 保证落在桶内：秒 + 毫秒最大值 < 60s，安全
    moment = moment.replace(microsecond=((index * 37) % 1000) * 1000)
    raw = render_line(spec, index, moment, level)
    return GeneratedEvent(
        raw_line=raw,
        event_time=moment,
        level=level,
        service=spec.service,
        format_key=spec.key,
        source_name=_source_name_for(spec),
    )


def generate_seeded_events(anchor_text: str) -> list[GeneratedEvent]:
    """6000 条已归类事件：每个格式 750 行，按设计好的桶内计数分布。"""
    current = current_bucket(anchor_text)
    events: list[GeneratedEvent] = []
    for spec in SEEDED_FORMATS:
        if spec.key == SPIKE_TEMPLATE_KEY:
            counts_head, older = _bucket_counts(EVENTS_PER_SEEDED_TEMPLATE, SPIKE_PATTERN, SPIKE_CURRENT_COUNT)
        else:
            counts_head, older = _bucket_counts(EVENTS_PER_SEEDED_TEMPLATE, FLAT_PATTERN, FLAT_CURRENT_COUNT)
        older_buckets = 131  # 12 小时 - 13 个设计桶
        older_counts = _distribute_older(older, older_buckets)
        index = 0
        # 先发当前桶
        for offset in range(counts_head[0]):
            level = "info"
            if spec.key == SPIKE_TEMPLATE_KEY:
                level = "error" if offset < 5 else "warn"
            elif spec.key == ERROR_RATIO_TEMPLATE_KEY:
                level = "error" if offset < ERROR_RATIO_CURRENT_ERRORS else "info"
            events.append(_emit(spec, index, current, offset * 17, level))
            index += 1
        for bucket_index, count in enumerate(counts_head[1:], start=1):
            bucket_at = current - timedelta(minutes=BUCKET_MINUTES * bucket_index)
            for offset in range(count):
                events.append(_emit(spec, index, bucket_at, offset * 19, spec.level_pattern))
                index += 1
        for bucket_index, count in enumerate(older_counts, start=13):
            bucket_at = current - timedelta(minutes=BUCKET_MINUTES * bucket_index)
            for offset in range(count):
                events.append(_emit(spec, index, bucket_at, offset * 23, spec.level_pattern))
                index += 1
        if index != EVENTS_PER_SEEDED_TEMPLATE:
            raise RuntimeError(f"{spec.key}: 生成 {index} 行，期望 {EVENTS_PER_SEEDED_TEMPLATE}")
    return events


def generate_pending_events(anchor_text: str) -> list[GeneratedEvent]:
    """240 行未归类新格式样本：3 种格式 × 5 个形态，含 1 个 error 尖峰形态。"""
    current = current_bucket(anchor_text)
    events: list[GeneratedEvent] = []
    for spec in NEW_FORMATS:
        plan = NEW_TEMPLATE_BUCKET_PLANS[spec.key]
        counts_head = [plan["current"], *plan["pattern"]]
        if sum(counts_head) != plan["total"]:
            raise RuntimeError(f"{spec.key}: 桶计划 {sum(counts_head)} 行，期望 {plan['total']}")
        older = 0
        index = 0
        for offset in range(counts_head[0]):
            level = "error" if offset < plan["current_errors"] else spec.level_pattern
            events.append(_emit(spec, index, current, offset * 29, level))
            index += 1
        for bucket_index, count in enumerate(counts_head[1:], start=1):
            bucket_at = current - timedelta(minutes=BUCKET_MINUTES * bucket_index)
            for offset in range(count):
                events.append(_emit(spec, index, bucket_at, offset * 31, spec.level_pattern))
                index += 1
        if index != plan["total"]:
            raise RuntimeError(f"{spec.key}: 生成 {index} 行，期望 {plan['total']}")
    if len(events) != PENDING_LINES_TOTAL:
        raise RuntimeError(f"pending 行数 {len(events)} != {PENDING_LINES_TOTAL}")
    return events


def build_import_sample_text(anchor_text: str) -> str:
    """249 行样本文件：9 行噪声 + 240 行新格式（乱序插入噪声，贴近真实粘贴的日志片段）。"""
    pending = generate_pending_events(anchor_text)
    lines: list[str] = []
    noise_positions = {0: 0, 2: 1, 40: 2, 41: 3, 42: 4, 120: 5, 121: 6, 180: 7, 248: 8}
    pending_index = 0
    for line_index in range(249):
        if line_index in noise_positions:
            lines.append(NOISE_LINES[noise_positions[line_index]])
            continue
        lines.append(pending[pending_index].raw_line)
        pending_index += 1
    return "\n".join(lines) + "\n"


def summarize_plans() -> dict:
    """供测试断言用的口径摘要。"""
    return {
        "seeded_formats": [spec.key for spec in SEEDED_FORMATS],
        "new_formats": [spec.key for spec in NEW_FORMATS],
        "seeded_events": EVENTS_PER_SEEDED_TEMPLATE * len(SEEDED_FORMATS),
        "pending_events": PENDING_LINES_TOTAL,
        "noise_lines": len(NOISE_LINES),
        "import_sample_lines": PENDING_LINES_TOTAL + len(NOISE_LINES),
        "spike_template": SPIKE_TEMPLATE_KEY,
        "error_ratio_template": ERROR_RATIO_TEMPLATE_KEY,
    }
