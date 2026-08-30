from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+psycopg2://dothours:dothours@localhost:5432/dothours"
    jwt_secret_key: str = "change-me-in-dot-env-file-please-32-chars-min"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    cors_origins: list[str] = ["http://localhost:5173"]

    # How long a cached leaderboard row is served before it is recomputed on read.
    leaderboard_ttl_seconds: int = 300

    # Realtime fan-out backend: "redis" across processes, "memory" inside one.
    ws_backend: str = "memory"

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Prometheus scrape endpoint at /metrics.
    metrics_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
