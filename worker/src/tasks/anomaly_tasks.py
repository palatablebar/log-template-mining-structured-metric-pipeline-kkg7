"""异常扫描任务：复用 backend.services.alert_service.run_scan（算法 B 落库）。"""
from __future__ import annotations

from worker_src.config.celery_app import celery_app

from src.config.database import session_scope
from src.services import alert_service
from src.utils.logger import get_logger

logger = get_logger("logmine.worker.anomaly")


@celery_app.task(name="logmine.scan_anomaly", bind=True, max_retries=2)
def scan_anomaly(self, actor: str = "worker") -> dict:
    try:
        with session_scope() as db:
            result = alert_service.run_scan(db, origin="worker", actor=actor)
        logger.info(
            "anomaly.scan templates=%s alerts=%s created=%s",
            result.get("templates_scanned"),
            len(result.get("alerts", [])),
            result.get("created"),
        )
        return {
            "bucket": result.get("bucket"),
            "templates_scanned": result.get("templates_scanned"),
            "created": result.get("created"),
            "insufficient_history": result.get("insufficient_history"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("scan anomaly failed: %s", exc)
        raise self.retry(exc=exc, countdown=30) from exc
