from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "LinkHub"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")

    # Database - use SQLite as fallback if PostgreSQL not available
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./linkhub.db")

    # Redis - optional for Railway free tier
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    REDIS_CACHE_TTL: int = 3600

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100

    # Celery
    CELERY_BROKER_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("REDIS_URL", "redis://localhost:6379/2")

    # Shortener
    SHORT_CODE_LENGTH: int = 6
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
