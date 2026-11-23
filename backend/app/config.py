from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+asyncpg://upsolve:upsolve@localhost:5432/upsolve"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev-only-change-me"
    jwt_ttl_days: int = 30
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]

    cf_base_url: str = "https://codeforces.com/api"
    # Codeforces asks API users to stay at or below one call every two seconds.
    cf_min_interval_seconds: float = 2.0
    cf_timeout_seconds: float = 30.0

    sync_cooldown_seconds: int = 600
    verification_ttl_seconds: int = 300
    analysis_cache_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
