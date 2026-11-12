"""幂等演示数据入口：`docker compose exec -T backend python -m scripts.seed_demo`。

自然键（重复执行只跳过、不覆盖用户修改）：
- users.email
- log_source.name
- parse_rule(source_id, name)
- log_template.signature
- log_event.line_hash（日志源 + 归一化原始行）
- alert_rule.name

演示数据集（与 SEED_SUMMARY 严格一致）：
  4 个日志源 / 8 条解析规则 / 8 个已挖掘模板 / 6240 条事件（6000 已归类 + 240 待归类新格式）
  / 3 条告警规则 / 2 条已触发告警 / 3 个用户。
"""
from __future__ import annotations

import sys
from datetime import timedelta

from sqlalchemy import func, insert, select

from src.config.bootstrap import ensure_schema
from src.config.database import session_scope
from src.config.settings import settings
from src.constants.enums import (
    AlertMetric,
    CollectStatus,
    EventLevel,
    LogFormat,
    TemplateStatus,
)
from src.constants.roles import ROLE_ADMIN, ROLE_ENGINEER, ROLE_VIEWER
from src.models.alert_event import AlertEvent
from src.models.alert_rule import AlertRule
from src.models.log_event import LogEvent
from src.models.log_source import LogSource
from src.models.log_template import LogTemplate
from src.models.parse_rule import ParseRule
from src.models.user import User
from src.services import alert_service, drain_engine
from src.utils.password import hash_password
from src.utils.text import line_hash, normalize_line, template_signature
from src.utils.time_buckets import bucket_start, parse_anchor
from scripts import fixtures

DEMO_PASSWORD = "Demo@2026"
ANCHOR = parse_anchor(settings.seed_anchor)

DEMO_USERS = (
    ("admin@logmine.demo", "云栖 IDC · SRE 负责人", ROLE_ADMIN),
    ("engineer@logmine.demo", "云栖 IDC · 值班工程师", ROLE_ENGINEER),
    ("viewer@logmine.demo", "云栖 IDC · 只读观察者", ROLE_VIEWER),
)

DEMO_SOURCES = (
    ("order-svc", "order-svc", LogFormat.KV.value, 4200, "idc-a/order-pool", "订单服务：下单/取消/状态变更，KV 风格行"),
    ("gateway-svc", "gateway-svc", LogFormat.PLAIN.value, 6100, "idc-a/gw-pool", "接入网关：路由、上游超时、熔断"),
    ("auth-svc", "auth-svc", LogFormat.SYSLOG.value, 2600, "idc-b/auth-pool", "认证服务：登录、令牌刷新"),
    ("pay-svc", "pay-svc", LogFormat.KV.value, 3100, "idc-b/pay-pool", "支付服务：扣款、结算批次"),
)

DEMO_RULES = (
    ("order-svc", "订单号提取", r"order_id=ORD-(?P<order_id>\d+)", ["order_id"], 10),
    ("order-svc", "渠道字段", r"channel=(?P<channel>[a-z_]+)", ["channel"], 20),
    ("gateway-svc", "状态码与耗时", r"status=(?P<status>\d{3})\s+elapsed_ms=(?P<elapsed_ms>\d+)", ["status", "elapsed_ms"], 10),
    ("gateway-svc", "上游目标", r"target=(?P<target>[a-z-]+)", ["target"], 20),
    ("auth-svc", "用户与会话", r"user=u-(?P<uid>\d+).*session=sess-(?P<session>\w+)", ["uid", "session"], 10),
    ("auth-svc", "客户端地址", r"ip=(?P<ip>\d{1,3}(?:\.\d{1,3}){3})", ["ip"], 20),
    ("pay-svc", "金额与币种", r"amount=(?P<amount>[\d.]+)\s+currency=(?P<currency>[A-Z]{3})", ["amount", "currency"], 10),
    ("pay-svc", "结算批次", r"batch=B-(?P<batch>\d+)", ["batch"], 20),
)

ALERT_RULES = (
    {
        "name": "全模板尖峰与错误占比突变",
        "template_key": None,
        "metric": AlertMetric.BOTH.value,
        "z_threshold": 3.5,
        "description": "对全部模板生效：z>3.5 或 error 占比 5%→25% 突升即触发，30 分钟去抖。",
    },
    {
        "name": "auth-svc 令牌刷新错误占比突变",
        "template_key": "auth_refresh",
        "metric": AlertMetric.ERROR_RATIO.value,
        "z_threshold": 3.5,
        "description": "认证服务 token refresh 模板：error 占比从 <5% 骤升 >25% 时告警。",
    },
    {
        "name": "gateway-svc 请求完成尖峰",
        "template_key": "gateway_completed",
        "metric": AlertMetric.SPIKE.value,
        "z_threshold": 3.5,
        "description": "网关请求完成模板：单桶计数相对 12 桶基线 z>3.5 时告警。",
    },
)

CREATED = 0
SKIPPED = 0


def _log(kind: str, entity: str, key: str) -> None:
    global CREATED, SKIPPED
    if kind == "SEED_CREATED":
        CREATED += 1
    else:
        SKIPPED += 1
    print(f"{kind} entity={entity} key={key}", flush=True)


def _upsert_users(db) -> None:
    for email, display_name, role in DEMO_USERS:
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing is not None:
            _log("SEED_SKIPPED", "user", email)
            continue
        db.add(
            User(
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                display_name=display_name,
                role=role,
                is_active=True,
            )
        )
        _log("SEED_CREATED", "user", email)
    db.flush()


def _upsert_sources(db) -> dict[str, LogSource]:
    sources: dict[str, LogSource] = {}
    for name, service, log_format, rate, host_group, description in DEMO_SOURCES:
        existing = db.execute(select(LogSource).where(LogSource.name == name)).scalar_one_or_none()
        if existing is None:
            existing = LogSource(
                name=name,
                service=service,
                log_format=log_format,
                collect_status=CollectStatus.ACTIVE.value,
                rate_per_min=rate,
                host_group=host_group,
                description=description,
                last_collected_at=ANCHOR,
            )
            db.add(existing)
            db.flush()
            _log("SEED_CREATED", "log_source", name)
        else:
            _log("SEED_SKIPPED", "log_source", name)
        sources[name] = existing
    return sources


def _upsert_parse_rules(db, sources: dict[str, LogSource]) -> None:
    hits = {"order-svc": 2941, "gateway-svc": 4188, "auth-svc": 1712, "pay-svc": 2087}
    for source_name, name, pattern, fields, priority in DEMO_RULES:
        source = sources[source_name]
        existing = db.execute(
            select(ParseRule).where(ParseRule.source_id == source.id, ParseRule.name == name)
        ).scalar_one_or_none()
        if existing is not None:
            _log("SEED_SKIPPED", "parse_rule", f"{source_name}/{name}")
            continue
        db.add(
            ParseRule(
                source_id=source.id,
                name=name,
                pattern=pattern,
                field_names=fields,
                priority=priority,
                enabled=True,
                hit_count=hits[source_name] // 2,
            )
        )
        _log("SEED_CREATED", "parse_rule", f"{source_name}/{name}")
    db.flush()


def _mine_seeded_templates(db) -> dict[str, LogTemplate]:
    """对 8 个格式各跑一次 Drain（真算），得到 8 个模板并落库。"""
    template_rows: dict[str, LogTemplate] = {}
    by_format: dict[str, list[str]] = {spec.key: [] for spec in fixtures.SEEDED_FORMATS}
    for event in fixtures.generate_seeded_events(settings.seed_anchor):
        by_format[event.format_key].append(event.raw_line)

    for spec in fixtures.SEEDED_FORMATS:
        lines = by_format[spec.key]
        result = drain_engine.DrainEngine().mine(lines)
        mined = [item for item in result.templates if item.status == TemplateStatus.MINED.value]
        if len(mined) != 1:
            raise RuntimeError(f"{spec.key}: Drain 期望 1 个模板，实得 {len(mined)}")
        template = mined[0]
        existing = db.execute(
            select(LogTemplate).where(LogTemplate.signature == template.signature)
        ).scalar_one_or_none()
        if existing is not None:
            _log("SEED_SKIPPED", "log_template", f"{spec.key}")
            template_rows[spec.key] = existing
            continue
        source = next((item for item in DEMO_SOURCES if item[1] == spec.service), None)
        source_row = None
        if source is not None:
            source_row = db.execute(select(LogSource).where(LogSource.name == source[0])).scalar_one_or_none()
        row = LogTemplate(
            signature=template.signature,
            template_str=template.template_str,
            token_count=template.token_count,
            slot_types=template.slot_types,
            slot_names=template.slot_names,
            source_id=source_row.id if source_row else None,
            service=spec.service,
            sample_line=template.sample_line,
            level_hint=template.level_hint,
            status=TemplateStatus.MINED.value,
            is_noise=False,
            frequency=len(lines),
            first_seen_at=ANCHOR - timedelta(hours=12),
            last_seen_at=ANCHOR,
            origin="seed",
            confirmed_by="",
        )
        db.add(row)
        db.flush()
        template_rows[spec.key] = row
        _log("SEED_CREATED", "log_template", f"{spec.key}")
    db.flush()
    return template_rows


def _insert_events(db, sources: dict[str, LogSource], templates: dict[str, LogTemplate]) -> None:
    source_by_service = {item[1]: sources[item[0]] for item in DEMO_SOURCES}
    rows: list[dict] = []
    for event in fixtures.generate_seeded_events(settings.seed_anchor):
        source = source_by_service.get(event.service)
        template = templates.get(event.format_key)
        if source is None or template is None:
            continue
        rows.append(
            {
                "source_id": source.id,
                "template_id": template.id,
                "raw_line": normalize_line(event.raw_line),
                "line_hash": line_hash(source.name, event.raw_line),
                "fields": {"tokens": len(drain_engine.tokenize(event.raw_line)), "seed": "classified"},
                "level": event.level,
                "event_time": event.event_time,
                "bucket_start": bucket_start(event.event_time),
                "origin": "seed",
                "service": event.service,
                "ingest_batch": "seed-classified",
            }
        )
    pending = fixtures.generate_pending_events(settings.seed_anchor)
    for event in pending:
        service_key = event.service.replace(".v2", "")
        source = source_by_service.get(service_key)
        if source is None:
            continue
        rows.append(
            {
                "source_id": source.id,
                "template_id": None,
                "raw_line": normalize_line(event.raw_line),
                "line_hash": line_hash(source.name, event.raw_line),
                "fields": {"tokens": len(drain_engine.tokenize(event.raw_line)), "seed": "pending"},
                "level": event.level,
                "event_time": event.event_time,
                "bucket_start": bucket_start(event.event_time),
                "origin": "seed",
                "service": event.service,
                "ingest_batch": "seed-pending",
            }
        )

    existing = int(db.execute(select(func.count()).select_from(LogEvent)).scalar_one())
    for start in range(0, len(rows), 500):
        chunk = rows[start : start + 500]
        db.execute(insert(LogEvent).prefix_with("IGNORE"), chunk)
        db.flush()
    after = int(db.execute(select(func.count()).select_from(LogEvent)).scalar_one())
    if after - existing:
        _log("SEED_CREATED", "log_event", f"+{after - existing}")
    else:
        _log("SEED_SKIPPED", "log_event", "0")
    # 模板频次按库里真实计数刷新
    for key, template in templates.items():
        stats_row = db.execute(
            select(func.count(), func.min(LogEvent.event_time), func.max(LogEvent.event_time)).where(
                LogEvent.template_id == template.id
            )
        ).first()
        if stats_row and stats_row[0]:
            template.frequency = int(stats_row[0])
            template.first_seen_at = stats_row[1]
            template.last_seen_at = stats_row[2]
    db.flush()


def _upsert_alert_rules(db, templates: dict[str, LogTemplate]) -> dict[str, AlertRule]:
    rules: dict[str, AlertRule] = {}
    for spec in ALERT_RULES:
        existing = db.execute(select(AlertRule).where(AlertRule.name == spec["name"])).scalar_one_or_none()
        if existing is not None:
            _log("SEED_SKIPPED", "alert_rule", spec["name"])
            rules[spec["name"]] = existing
            continue
        template = templates.get(spec["template_key"]) if spec["template_key"] else None
        rule = AlertRule(
            name=spec["name"],
            template_id=template.id if template else None,
            metric=spec["metric"],
            window_minutes=5,
            baseline_buckets=12,
            z_threshold=spec["z_threshold"],
            error_ratio_low=0.05,
            error_ratio_high=0.25,
            silence_minutes=30,
            enabled=True,
            description=spec["description"],
            created_by="admin@logmine.demo",
        )
        db.add(rule)
        db.flush()
        rules[spec["name"]] = rule
        _log("SEED_CREATED", "alert_rule", spec["name"])
    db.flush()
    return rules


def _scan_alerts(db) -> None:
    """seed 内跑一次真实异常扫描：T3 尖峰 + T6 错误占比 → 2 条告警。"""
    before = int(db.execute(select(func.count()).select_from(AlertEvent)).scalar_one())
    result = alert_service.run_scan(db, origin="seed")
    after = int(db.execute(select(func.count()).select_from(AlertEvent)).scalar_one())
    if after > before:
        _log("SEED_CREATED", "alert_event", f"+{after - before}")
    else:
        _log("SEED_SKIPPED", "alert_event", f"created={result.get('created', 0)}")
    db.flush()


def _write_sample_file() -> None:
    """把 249 行样本写到 /data/samples（容器卷），便于 curl -F 或人工查看。"""
    try:
        from pathlib import Path

        directory = Path(settings.sample_dir)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "new_format_249.log").write_text(fixtures.build_import_sample_text(settings.seed_anchor), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - 样本落盘失败不影响 seed
        print(f"SEED_WARN sample_file_failed {exc}", file=sys.stderr, flush=True)


def seed_all() -> dict:
    ensure_schema()
    with session_scope() as db:
        _upsert_users(db)
        sources = _upsert_sources(db)
        _upsert_parse_rules(db, sources)
        templates = _mine_seeded_templates(db)
        _insert_events(db, sources, templates)
        _upsert_alert_rules(db, templates)
        _scan_alerts(db)
        _write_sample_file()

        counts = {
            "sources": int(db.execute(select(func.count()).select_from(LogSource)).scalar_one()),
            "rules": int(db.execute(select(func.count()).select_from(ParseRule)).scalar_one()),
            "templates": int(
                db.execute(select(func.count()).select_from(LogTemplate).where(LogTemplate.origin == "seed")).scalar_one()
            ),
            "events": int(
                db.execute(select(func.count()).select_from(LogEvent).where(LogEvent.origin == "seed")).scalar_one()
            ),
            "alerts": int(
                db.execute(select(func.count()).select_from(AlertEvent).where(AlertEvent.origin == "seed")).scalar_one()
            ),
            "users": int(db.execute(select(func.count()).select_from(User)).scalar_one()),
        }
    summary = " ".join(f"{key}={value}" for key, value in counts.items())
    print(f"SEED_SUMMARY {summary}", flush=True)
    return {"created": CREATED, "skipped": SKIPPED, "counts": counts}


if __name__ == "__main__":
    seed_all()
