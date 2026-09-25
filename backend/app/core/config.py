from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: SecretStr = SecretStr("postgresql+psycopg://ai_farm@127.0.0.1:5432/ai_farm")
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    agent_a_starting_balance: Decimal = Field(
        default=Decimal("1000.00"), gt=0, max_digits=18, decimal_places=2
    )
    agent_b_starting_balance: Decimal = Field(
        default=Decimal("1000.00"), gt=0, max_digits=18, decimal_places=2
    )
    heartbeat_interval_seconds: float = Field(default=5, ge=1, le=60)
    openai_api_key: SecretStr | None = None
    market_data_api_key: SecretStr | None = None
    discord_webhook_url: SecretStr | None = None
    ai_monthly_budget_usd: Decimal | None = Field(default=None, ge=0)

    @field_validator("ai_monthly_budget_usd", mode="before")
    @classmethod
    def blank_budget_is_unconfigured(cls, value):
        return None if value == "" else value

    @field_validator("cors_origins")
    @classmethod
    def explicit_origins_only(cls, origins: list[str]) -> list[str]:
        if any(
            origin == "*" or not origin.startswith(("http://", "https://")) for origin in origins
        ):
            raise ValueError("CORS requires explicit http(s) origins")
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
