import os
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "LinkHub"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./linkhub.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    REDIS_CACHE_TTL: int = 3600
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    RATE_LIMIT_PER_MINUTE: int = 100
    SHORT_CODE_LENGTH: int = 6
    BASE_URL: str = os.getenv("BASE_URL", "")

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
