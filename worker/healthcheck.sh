#!/bin/sh
# worker 健康检查：优先 Redis 心跳键（beat 每 30s 写），兜底 celery inspect ping。
cd /app || exit 1
python - <<'PY'
import os
import sys
import time

os.environ.setdefault("PYTHONPATH", "/app:/app/backend")
sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app")

import redis

URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


def heartbeat_ok() -> bool:
    try:
        client = redis.Redis.from_url(URL, decode_responses=True)
        value = client.get("logmine:worker:heartbeat")
        if not value:
            return False
        return (time.time() - float(value)) < 90
    except Exception:
        return False


def celery_ok() -> bool:
    try:
        from worker_src.config.celery_app import celery_app

        return bool(celery_app.control.ping(timeout=3))
    except Exception:
        return False


if heartbeat_ok() or celery_ok():
    print("worker healthy")
    sys.exit(0)
print("worker unhealthy: no heartbeat and no celery pong")
sys.exit(1)
PY
