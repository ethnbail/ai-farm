from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url.get_secret_value()
    connect_args = (
        {"check_same_thread": False} if url.startswith("sqlite") else {"connect_timeout": 3}
    )
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
