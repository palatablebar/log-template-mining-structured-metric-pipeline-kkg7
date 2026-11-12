"""集中配置：全部来自环境变量，默认值与 .env.example 保持一致。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # MySQL
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "logmine"
    db_user: str = "logmine"
    db_password: str = "logmine_pw_2026"

    # 安全
    jwt_secret: str = "logmine-jwt-secret-change-me-2026"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 120
    refresh_token_days: int = 7

    # 运行时
    redis_url: str = "redis://localhost:6379/0"
    sample_dir: str = "/data/samples"
    max_upload_mb: int = 8
    seed_demo: bool = True
    seed_anchor: str = "2026-11-10T15:05:00"

    # 限流 / 配额
    rate_limit_per_minute: int = 120
    daily_quota_admin: int = 8000
    daily_quota_engineer: int = 4000
    daily_quota_viewer: int = 2000

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
