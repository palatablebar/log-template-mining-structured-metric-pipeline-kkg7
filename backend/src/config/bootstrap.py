"""容器启动建表：导入全部 model 后 create_all（幂等）。

MySQL 建表比 Alembic 迁移轻，demo 迭代期用这一份；`migrations/` 目录保留给后续演进。
"""
from __future__ import annotations

from sqlalchemy import text

from src.config.database import engine
from src.models import Base  # noqa: F401  (Base 聚合所有 model)
import src.models.alert_event  # noqa: F401
import src.models.alert_rule  # noqa: F401
import src.models.audit_log  # noqa: F401
import src.models.log_event  # noqa: F401
import src.models.log_source  # noqa: F401
import src.models.log_template  # noqa: F401
import src.models.parse_rule  # noqa: F401
import src.models.user  # noqa: F401
from src.utils.logger import get_logger

logger = get_logger("logmine.bootstrap")


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("schema ready tables=%s", len(Base.metadata.tables))


if __name__ == "__main__":
    ensure_schema()
