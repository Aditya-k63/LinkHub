"""Application configuration.

Every setting is resolved from the environment (or a local ``.env`` file)
through pydantic-settings, so a misconfigured deployment fails at import
time instead of at the first request.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Placeholder secrets that must never be used outside local development.
INSECURE_SECRETS = frozenset(
    {
        "change-me",
        "change-me-to-random-string",
        "jwt-secret-change-me",
        "secret",
        "string",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Application ----------------------------------------------------
    APP_NAME: str = "LinkHub"
    APP_VERSION: str = "1.1.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False

    # --- Security -------------------------------------------------------
    SECRET_KEY: str = "change-me"
    JWT_SECRET_KEY: str = "jwt-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- Storage --------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./linkhub.db"
    REDIS_URL: str = ""
    REDIS_CACHE_TTL: int = 3600

    # --- Behaviour ------------------------------------------------------
    RATE_LIMIT_PER_MINUTE: int = 100
    SHORT_CODE_LENGTH: int = 6
    BASE_URL: str = ""
    CORS_ORIGINS: str = ""
    TRUSTED_HOSTS: str = ""

    # --- Click pipeline -------------------------------------------------
    # ``sync`` writes the click inline (correct with zero extra infra).
    # ``async`` pushes the click onto Redis and lets a worker persist it.
    CLICK_WRITE_MODE: str = "sync"  # sync | async
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        """Origins allowed to call the API from a browser."""
        if self.CORS_ORIGINS:
            return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.is_production:
            # No wildcard in production: an open CORS policy lets any site
            # read authenticated responses from a logged-in visitor.
            return []
        return [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
        ]

    @property
    def trusted_hosts(self) -> list[str]:
        """Hosts accepted in the Host header."""
        if self.TRUSTED_HOSTS:
            return [h.strip() for h in self.TRUSTED_HOSTS.split(",") if h.strip()]
        return [] if self.is_production else ["*"]

    @property
    def public_base_url(self) -> str:
        """Absolute base used when building short URLs."""
        if self.BASE_URL:
            return self.BASE_URL.rstrip("/")
        return "http://localhost:8000"

    @property
    def click_write_mode(self) -> str:
        mode = (self.CLICK_WRITE_MODE or "sync").strip().lower()
        return mode if mode in {"sync", "async"} else "sync"

    def validate_runtime(self) -> None:
        """Reject configurations that are unsafe in production.

        Called during application startup. Failing here is far better than
        serving forgeable admin tokens for the lifetime of the process.
        """
        if not self.is_production:
            return

        problems: list[str] = []
        if self.SECRET_KEY in INSECURE_SECRETS:
            problems.append("SECRET_KEY is still the default value")
        if self.JWT_SECRET_KEY in INSECURE_SECRETS:
            problems.append("JWT_SECRET_KEY is still the default value")
        elif len(self.JWT_SECRET_KEY) < 32:
            problems.append("JWT_SECRET_KEY must be at least 32 characters")
        if self.DEBUG:
            problems.append("DEBUG must be false in production")
        if not self.BASE_URL:
            problems.append("BASE_URL must be set so short links resolve to the public host")
        if not self.CORS_ORIGINS:
            problems.append("CORS_ORIGINS must be set explicitly in production")

        if problems:
            raise RuntimeError(
                "Refusing to start with an unsafe production configuration: " + "; ".join(problems)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
