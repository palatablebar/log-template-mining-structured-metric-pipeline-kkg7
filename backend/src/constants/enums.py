"""共享枚举（后端唯一来源）。前端 `constants/enums.ts` 必须与之逐项一致。

出现位置：
- ROLE_*：models/user.py、middlewares/rbac.py、seed_demo.py、routes/auth.py
- LogFormat：models/log_source.py、services/source_service.py、schemas/source.py
- CollectStatus：models/log_source.py、services/source_service.py
- TemplateStatus：models/log_template.py、services/drain_engine.py、services/template_service.py
- SlotType：services/drain_engine.py、services/template_service.py（落 template.slot_types）
- EventLevel：models/log_event.py、services/drain_engine.py、services/anomaly_engine.py
- TriggerReason：models/alert_event.py、services/anomaly_engine.py
- AlertStatus：models/alert_event.py、services/alert_service.py
"""
from __future__ import annotations

from enum import StrEnum


class LogFormat(StrEnum):
    PLAIN = "plain"
    JSON = "json"
    KV = "kv"
    SYSLOG = "syslog"


class CollectStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class TemplateStatus(StrEnum):
    MINED = "mined"           # 已挖掘（样本 >= 2）
    TENTATIVE = "tentative"   # 样本 < 2，待确认
    CONFIRMED = "confirmed"   # 人工确认
    NOISE = "noise"           # _noise 模板：空行/纯符号行


class SlotType(StrEnum):
    NUM = "num"
    IP = "ip"
    UUID = "uuid"
    PATH = "path"
    HEX = "hex"
    TS = "ts"
    STR = "str"
    UNKNOWN = "unknown"


class EventLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class TriggerReason(StrEnum):
    SPIKE = "spike_zscore"
    ERROR_RATIO = "error_ratio_jump"
    BOTH = "spike_and_error_ratio"


class AlertStatus(StrEnum):
    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    SILENCED = "silenced"
    RESOLVED = "resolved"


class AlertMetric(StrEnum):
    SPIKE = "spike"
    ERROR_RATIO = "error_ratio"
    BOTH = "both"


class ImportStatus(StrEnum):
    PREVIEW = "preview"
    APPLIED = "applied"


ROLE_ADMIN = "admin"
ROLE_ENGINEER = "engineer"
ROLE_VIEWER = "viewer"
ALL_ROLES: tuple[str, ...] = (ROLE_ADMIN, ROLE_ENGINEER, ROLE_VIEWER)

ROLE_LABELS: dict[str, str] = {
    ROLE_ADMIN: "SRE 负责人",
    ROLE_ENGINEER: "值班工程师",
    ROLE_VIEWER: "只读观察者",
}

EVENT_LEVELS: tuple[str, ...] = tuple(level.value for level in EventLevel)
TEMPLATE_STATUSES: tuple[str, ...] = tuple(status.value for status in TemplateStatus)
