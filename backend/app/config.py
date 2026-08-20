"""Application settings loaded from environment variables."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "AI Sales Dashboard"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://dashboard:dashboard@localhost:5432/dashboard"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Rate limiting (per user per window)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 120
    RATE_LIMIT_AUTH_PER_MINUTE: int = 20

    # Observability
    SENTRY_DSN: str = ""

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Google Sheets (service account JSON path)
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    SHEETS_ORDERS_ID: str = "1_-k6B8LfGeW6ayT3-gfPT_2IJEW7kf4pqFa8tubrDA0"
    SHEETS_ORDERS_TAB: str = "Commandes"
    SHEETS_PRODUCTS_ID: str = "1PDfe5zGhGMoveWaM9gdNZmiksMeDUDnVVAFIOadDp3Q"
    SHEETS_PRODUCTS_TAB: str = "الورقة1"
    SHEETS_POSTS_ID: str = "1CbDGkABKJG1Jq9SuAeJHiEY7Hf_Uo_OvrKe1GwoDQ3o"
    SHEETS_POSTS_TAB: str = "الورقة1"

    # Sync
    SYNC_ORDERS_INTERVAL_SECONDS: int = 30
    SYNC_PRODUCTS_INTERVAL_SECONDS: int = 60
    RECONCILE_INTERVAL_SECONDS: int = 300

    # Legacy Google Sheets compatibility (temporary; PostgreSQL is the source of truth)
    # When False, the legacy adapter is fully inert: zero sheet I/O, all features
    # operate on PostgreSQL alone.
    SHEETS_COMPAT_MODE: bool = True

    # Storage (S3-compatible object storage; local fallback for development)
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_DIR: str = "storage/media"
    S3_ENDPOINT: str = ""
    S3_BUCKET: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = ""
    S3_PUBLIC_BASE_URL: str = ""

    # Couriers / tracking
    TRACKING_POLL_INTERVAL_SECONDS: int = 300
    TRACKING_STALE_MINUTES: int = 30
    DEFAULT_FROM_WILAYA: str = "Alger"
    YALIDINE_API_BASE_URL: str = "https://api.yalidine.app/v1"

    # Feature toggles
    RETURNS_ENABLED: bool = True
    SHIPMENTS_ENABLED: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()