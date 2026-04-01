"""Application configuration loaded from environment and optional `.env` file."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "api-comerce-in"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/ecommerce"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires_minutes: int = 30
    admin_email: str = "you@example.com"

    stripe_secret_key: str = "sk_test_xxx"
    stripe_webhook_secret: str = "whsec_xxx"

    @model_validator(mode="after")
    def jwt_secret_strong_in_prod(self):
        if self.app_env.lower() == "prod" and self.jwt_secret in ("change-me", ""):
            msg = "JWT_SECRET must be set to a strong value when APP_ENV=prod"
            raise ValueError(msg)
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings loaded from environment."""
    return Settings()
