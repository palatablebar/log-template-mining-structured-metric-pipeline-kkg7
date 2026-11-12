# migrations

logmine 的表结构以 `backend/src/models/` 的 SQLAlchemy 2.0 声明为唯一来源，
容器启动时 `python -m src.config.bootstrap` 执行 `metadata.create_all()` 幂等建表。

第一批迭代刻意不引入 Alembic（中型 demo、单库、无演进需求），后续需要做列迁移时
在本目录补 `env.py` + `versions/`，并把 bootstrap 的 create_all 收敛到迁移脚本。
