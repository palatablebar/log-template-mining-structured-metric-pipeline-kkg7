"""模板挖掘任务：读取样本文件 → Drain → 落库（复用 backend.services.import_service）。"""
from __future__ import annotations

from pathlib import Path

from worker_src.config.celery_app import celery_app

from src.config.database import session_scope
from src.config.settings import settings
from src.services import import_service
from src.utils.logger import get_logger

logger = get_logger("logmine.worker.mine")


@celery_app.task(name="logmine.mine_templates", bind=True, max_retries=2)
def mine_templates(self, sample_path: str = "", actor: str = "worker") -> dict:
    try:
        path = Path(sample_path or (Path(settings.sample_dir) / "new_format_249.log"))
        text = path.read_text(encoding="utf-8")
        with session_scope() as db:
            result = import_service.apply_text(db, text, actor=actor)
        logger.info(
            "drain.run lines=%s new_templates=%s coverage=%s",
            result.get("lines_total"),
            result.get("new_templates"),
            result.get("coverage"),
        )
        return {
            "lines_total": result.get("lines_total"),
            "new_templates": result.get("new_templates"),
            "coverage": result.get("coverage"),
            "assigned_events": result.get("assigned_events"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("mine templates failed: %s", exc)
        raise self.retry(exc=exc, countdown=30) from exc
