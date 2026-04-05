"""Application configuration loaded from environment and optional `.env` file."""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "api-comerce-in"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/ecommerce"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires_minutes: int = 30
    admin_email: str = "you@example.com"

    stripe_secret_key: str = Field(
        default="sk_test_xxx",
        description="Stripe API secret (STRIPE_SECRET_KEY); use sk_test_* in dev, sk_live_* in prod.",
    )
    stripe_webhook_secret: str = Field(
        default="whsec_xxx",
        description=(
            "Signing secret for webhook signature verification (STRIPE_WEBHOOK_SECRET). "
            "Use the secret from Stripe Dashboard or from `stripe listen` locally."
        ),
    )
    stripe_checkout_success_url: str = Field(
        default="http://localhost:3000/checkout/success?session_id={CHECKOUT_SESSION_ID}",
        description="Stripe Checkout success_url (STRIPE_CHECKOUT_SUCCESS_URL).",
    )
    stripe_checkout_cancel_url: str = Field(
        default="http://localhost:3000/checkout/cancel",
        description="Stripe Checkout cancel_url (STRIPE_CHECKOUT_CANCEL_URL).",
    )

    @model_validator(mode="after")
    def jwt_secret_strong_in_prod(self):
        if self.app_env.lower() == "prod" and self.jwt_secret in ("change-me", ""):
            msg = "JWT_SECRET must be set to a strong value when APP_ENV=prod"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def stripe_secrets_sane_in_prod(self):
        if self.app_env.lower() != "prod":
            return self
        key = self.stripe_secret_key.strip()
        if not key or key == "sk_test_xxx" or key.startswith("sk_test"):
            msg = "STRIPE_SECRET_KEY must be a live key (sk_live_...) when APP_ENV=prod"
            raise ValueError(msg)
        wh = self.stripe_webhook_secret.strip()
        if not wh or wh == "whsec_xxx":
            msg = "STRIPE_WEBHOOK_SECRET must be set to your endpoint signing secret when APP_ENV=prod"
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
