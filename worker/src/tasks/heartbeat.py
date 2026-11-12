"""心跳任务：beat 每 30s 写 Redis 键，healthcheck 读它判活。"""
from __future__ import annotations

import time

from worker_src.config.celery_app import celery_app

from src.utils.redis_client import get_redis
from src.utils.logger import get_logger

logger = get_logger("logmine.worker.heartbeat")


@celery_app.task(name="logmine.heartbeat")
def heartbeat() -> dict:
    try:
        get_redis().set("logmine:worker:heartbeat", time.time(), ex=180)
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat failed: %s", exc)
        return {"ok": False, "error": str(exc)}
