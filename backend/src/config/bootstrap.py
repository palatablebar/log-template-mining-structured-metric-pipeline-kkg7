"""容器启动建表：导入全部 model 后 create_all（幂等）。

MySQL 建表比 Alembic 迁移轻，demo 迭代期用这一份；`migrations/` 目录保留给后续演进。
"""
from __future__ import annotations

from sqlalchemy import text

from src.config.database import engine
from src.models import Base  # noqa: F401  (Base 聚合所有 model)
import src.models.alert_event  # noqa: F401
import src.models.alert_recompute  # noqa: F401
import src.models.alert_rule  # noqa: F401
import src.models.audit_log  # noqa: F401
import src.models.log_event  # noqa: F401
import src.models.log_source  # noqa: F401
import src.models.log_template  # noqa: F401
import src.models.parse_rule  # noqa: F401
import src.models.user  # noqa: F401
from src.utils.logger import get_logger

logger = get_logger("logmine.bootstrap")


def _ensure_legacy_indexes() -> None:
    """对已存在的旧库补幂等 DDL（create_all 不会给老表加新约束/列/索引）。

    - alert_event.recompute_count：补算次数列；
    - uq_alert_template_bucket：保证同一 (模板, 时间桶) 只有一条告警，
      补算靠它做幂等 upsert；存量若有重复行先去重（保留最早一条）。
    """
    with engine.begin() as conn:
        column_exists = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'alert_event' "
                "AND column_name = 'recompute_count' LIMIT 1"
            )
        ).first()
        if not column_exists:
            conn.execute(
                text("ALTER TABLE alert_event ADD COLUMN recompute_count INT NOT NULL DEFAULT 0")
            )
        duplicates = conn.execute(
            text(
                "SELECT template_id, bucket_start, COUNT(*) AS c FROM alert_event "
                "GROUP BY template_id, bucket_start HAVING c > 1"
            )
        ).all()
        for template_id, bucket_start, _count in duplicates:
            conn.execute(
                text(
                    "DELETE FROM alert_event WHERE template_id = :tid AND bucket_start = :bucket "
                    "AND id NOT IN (SELECT min_id FROM ("
                    "SELECT MIN(id) AS min_id FROM alert_event "
                    "WHERE template_id = :tid AND bucket_start = :bucket) AS keep)"
                ),
                {"tid": template_id, "bucket": bucket_start},
            )
        exists = conn.execute(
            text(
                "SELECT 1 FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'alert_event' "
                "AND index_name = 'uq_alert_template_bucket' LIMIT 1"
            )
        ).first()
        if not exists:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX uq_alert_template_bucket "
                    "ON alert_event (template_id, bucket_start)"
                )
            )


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_legacy_indexes()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("schema ready tables=%s", len(Base.metadata.tables))


if __name__ == "__main__":
    ensure_schema()
