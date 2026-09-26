from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.market_data.mock import MockMarketDataProvider
from app.market_data.tradier import TradierMarketDataProvider
from app.market_data.types import DataUnavailable
from app.models import MarketState


def get_provider(session: Session, settings: Settings, now: datetime):
    if (
        settings.market_data_provider == "tradier"
        and settings.market_data_api_key
        and settings.market_data_api_key.get_secret_value().strip()
    ):
        return TradierMarketDataProvider(settings, now)
    if settings.market_data_provider not in {"mock", "tradier"}:
        # Keys alone never opt into a provider or silently relabel mock data as live.
        raise DataUnavailable("Provider is not implemented; select MARKET_DATA_PROVIDER=mock")
    state = session.get(MarketState, 1)
    if state is None:
        raise DataUnavailable("Mock market state is missing; run migrations")
    return MockMarketDataProvider(state.tick, state.scenario, now)
