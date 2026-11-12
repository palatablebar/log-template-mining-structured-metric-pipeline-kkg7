"""每日写配额：按 (角色, 日期) 在 Redis 累加；超限抛 429。"""
from __future__ import annotations

from datetime import date

from src.config.settings import settings
from src.constants import error_codes as codes
from src.constants.enums import ROLE_ADMIN, ROLE_ENGINEER, ROLE_VIEWER
from src.utils.errors import AppError
from src.utils.redis_client import get_redis

QUOTA_BY_ROLE: dict[str, int] = {
    ROLE_ADMIN: settings.daily_quota_admin,
    ROLE_ENGINEER: settings.daily_quota_engineer,
    ROLE_VIEWER: settings.daily_quota_viewer,
}


def consume(user_id: int, role: str, amount: int = 1) -> tuple[int, int]:
    """消耗配额，返回 (已用, 上限)。Redis 不可用时放行（不阻塞主流程）。"""
    limit = QUOTA_BY_ROLE.get(role, settings.daily_quota_viewer)
    key = f"logmine:quota:{user_id}:{date.today().isoformat()}"
    try:
        client = get_redis()
        used = int(client.incrby(key, amount))
        if used == amount:
            client.expire(key, 60 * 60 * 26)
    except Exception:
        return (0, limit)
    if used > limit:
        raise AppError(
            codes.DAILY_QUOTA_EXCEEDED,
            f"今日写操作配额已用尽（{used}/{limit}）",
            f"user_id={user_id} role={role} used={used} limit={limit}",
            extra={"used": used, "limit": limit},
        )
    return (used, limit)


def peek(user_id: int, role: str) -> dict:
    limit = QUOTA_BY_ROLE.get(role, settings.daily_quota_viewer)
    key = f"logmine:quota:{user_id}:{date.today().isoformat()}"
    try:
        used = int(get_redis().get(key) or 0)
    except Exception:
        used = 0
    return {"used": used, "limit": limit, "remaining": max(0, limit - used), "date": date.today().isoformat()}
