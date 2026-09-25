from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
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
    trading_mode: str = "paper"
    market_data_provider: str = "mock"
    paper_worker_enabled: bool = False
    enable_development_actions: bool = False
    regular_hours_only: bool = True
    quote_max_age_seconds: int = Field(default=60, ge=1, le=3600)
    equity_slippage_bps: Decimal = Field(default=Decimal("5"), ge=0, le=500)
    option_slippage_percent: Decimal = Field(default=Decimal("1"), ge=0, le=25)
    max_risk_per_trade_percent: Decimal = Field(default=Decimal("2"), gt=0, le=100)
    max_position_size_percent: Decimal = Field(default=Decimal("20"), gt=0, le=100)
    max_open_positions: int = Field(default=3, ge=1, le=100)
    max_options_positions: int = Field(default=2, ge=1, le=100)
    max_daily_loss_percent: Decimal = Field(default=Decimal("5"), gt=0, le=100)
    max_weekly_loss_percent: Decimal = Field(default=Decimal("10"), gt=0, le=100)
    max_total_exposure_percent: Decimal = Field(default=Decimal("60"), gt=0, le=100)
    min_cash_reserve_percent: Decimal = Field(default=Decimal("10"), ge=0, lt=100)
    max_option_premium_at_risk_percent: Decimal = Field(default=Decimal("2"), gt=0, le=100)
    min_option_dte: int = Field(default=7, ge=1)
    max_option_dte: int = Field(default=45, ge=1, le=365)
    min_option_volume: int = Field(default=50, ge=0)
    min_option_open_interest: int = Field(default=100, ge=0)
    max_option_spread_percent: Decimal = Field(default=Decimal("15"), gt=0, le=100)
    target_option_delta_min: Decimal = Field(default=Decimal("0.40"), ge=0, le=1)
    target_option_delta_max: Decimal = Field(default=Decimal("0.70"), ge=0, le=1)
    max_option_iv: Decimal = Field(default=Decimal("3"), gt=0)
    max_option_theta_decay_percent: Decimal = Field(default=Decimal("20"), gt=0, le=100)
    equity_scan_interval_seconds: int = Field(default=60, ge=10)
    options_scan_interval_seconds: int = Field(default=60, ge=10)
    position_monitor_interval_seconds: int = Field(default=15, ge=5)
    strategy_fast_window: int = Field(default=5, ge=2, le=50)
    strategy_slow_window: int = Field(default=20, ge=3, le=100)
    equity_stop_percent: Decimal = Field(default=Decimal("2"), gt=0, lt=100)
    equity_target_percent: Decimal = Field(default=Decimal("4"), gt=0)
    option_stop_percent: Decimal = Field(default=Decimal("30"), gt=0, lt=100)
    option_target_percent: Decimal = Field(default=Decimal("50"), gt=0)
    minimum_performance_trades: int = Field(default=5, ge=5)

    @model_validator(mode="after")
    def ordered_ranges(self):
        if self.min_option_dte > self.max_option_dte:
            raise ValueError("Minimum DTE cannot exceed maximum DTE")
        if self.target_option_delta_min > self.target_option_delta_max:
            raise ValueError("Minimum delta cannot exceed maximum delta")
        if self.strategy_fast_window >= self.strategy_slow_window:
            raise ValueError("Fast moving average window must be shorter than slow window")
        return self

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
