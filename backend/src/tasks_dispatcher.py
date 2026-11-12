"""backend 侧的 Celery 投递封装（任务本体在 worker 容器里）。"""
from __future__ import annotations

from src.config.celery_app import TASK_MINE_TEMPLATES, TASK_SCAN_ANOMALY, celery_app


def dispatch_scan(actor: str = "system") -> str | None:
    try:
        result = celery_app.send_task(TASK_SCAN_ANOMALY, kwargs={"actor": actor})
        return result.id
    except Exception:
        return None


def dispatch_mine(sample_path: str, actor: str = "system") -> str | None:
    try:
        result = celery_app.send_task(TASK_MINE_TEMPLATES, kwargs={"sample_path": sample_path, "actor": actor})
        return result.id
    except Exception:
        return None
