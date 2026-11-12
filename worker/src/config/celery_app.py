"""worker 侧 Celery 应用：复用 backend 的 settings 与服务层，注册两个任务。"""
from __future__ import annotations

import sys

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app")

from celery import Celery
from celery.schedules import crontab

from src.config.settings import settings  # backend 包

celery_app = Celery(
    "logmine-worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker_src.tasks.anomaly_tasks", "worker_src.tasks.mine_tasks", "worker_src.tasks.heartbeat"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "heartbeat-every-30s": {"task": "logmine.heartbeat", "schedule": 30.0},
        "scan-anomaly-every-5min": {"task": "logmine.scan_anomaly", "schedule": 300.0, "kwargs": {"actor": "worker-beat"}},
    },
)
