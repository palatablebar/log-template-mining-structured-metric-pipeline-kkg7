"""补传补算任务：复用 backend.services.alert_service.run_recompute（只重算受影响模板 × 桶）。"""
from __future__ import annotations

from worker_src.config.celery_app import celery_app

from src.config.database import session_scope
from src.services import alert_service
from src.utils.logger import get_logger

logger = get_logger("logmine.worker.recompute")


@celery_app.task(name="logmine.recompute_alerts", bind=True, max_retries=2)
def recompute_alerts(
    self,
    actor: str = "worker",
    start: str | None = None,
    end: str | None = None,
    template_ids: list[int] | None = None,
    idempotency_key: str = "",
) -> dict:
    try:
        with session_scope() as db:
            result = alert_service.run_recompute(
                db,
                actor=actor,
                start=start,
                end=end,
                template_ids=template_ids,
                idempotency_key=idempotency_key,
            )
        logger.info(
            "alerts.recompute job_id=%s pairs=%s created=%s updated=%s resolved=%s deduplicated=%s",
            result.get("id"),
            result.get("pair_count"),
            result.get("created"),
            result.get("updated"),
            result.get("resolved"),
            result.get("deduplicated"),
        )
        return {
            "id": result.get("id"),
            "pair_count": result.get("pair_count"),
            "created": result.get("created"),
            "updated": result.get("updated"),
            "resolved": result.get("resolved"),
            "deduplicated": result.get("deduplicated", False),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("recompute alerts failed: %s", exc)
        raise self.retry(exc=exc, countdown=30) from exc
