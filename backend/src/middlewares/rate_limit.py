"""限流（Redis 滑动窗口，每用户每分钟）+ 每日写配额。超限统一 429。"""
from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Depends, Request

from src.config.settings import settings
from src.constants import error_codes as codes
from src.constants.limits import RATE_LIMIT_SCAN_PER_MINUTE, RATE_LIMIT_WRITE_PER_MINUTE
from src.middlewares.auth import get_current_user
from src.models.user import User
from src.services.quota_service import consume as consume_quota
from src.utils.errors import AppError
from src.utils.redis_client import get_redis

WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def _sliding_window(key: str, limit: int, window_seconds: int = 60) -> int:
    now = time.time()
    client = get_redis()
    pipeline = client.pipeline()
    pipeline.zremrangebyscore(key, 0, now - window_seconds)
    pipeline.zadd(key, {f"{now}-{id(pipeline)}": now})
    pipeline.zcard(key)
    pipeline.expire(key, window_seconds)
    results = pipeline.execute()
    count = int(results[2])
    if count > limit:
        raise AppError(
            codes.RATE_LIMITED,
            "请求过于频繁，请稍后重试",
            f"key={key} count={count} limit={limit}",
            extra={"retry_after": window_seconds},
        )
    return count


def guard(bucket: str = "default") -> Callable[..., None]:
    """通用守卫：每用户每分钟限流（读写不同阈值）；写请求额外扣每日配额。"""

    def dependency(request: Request, user: User = Depends(get_current_user)) -> None:
        limit = RATE_LIMIT_SCAN_PER_MINUTE if bucket == "scan" else (
            RATE_LIMIT_WRITE_PER_MINUTE if request.method in WRITE_METHODS else settings.rate_limit_per_minute
        )
        try:
            _sliding_window(f"logmine:ratelimit:{bucket}:{user.id}:{request.url.path}", limit)
        except AppError:
            raise
        except Exception:
            # Redis 抖动不阻塞业务（限流是保护，不是正确性依赖）
            pass
        if request.method in WRITE_METHODS:
            consume_quota(user.id, user.role)

    return Depends(dependency)
