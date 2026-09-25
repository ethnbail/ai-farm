from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_engine


@pytest.fixture
def database(monkeypatch, tmp_path):
    # Every test migrates its own disposable DB; never touch a developer's PostgreSQL DB.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("AGENT_A_STARTING_BALANCE", "1000.00")
    monkeypatch.setenv("AGENT_B_STARTING_BALANCE", "1000.00")
    get_settings.cache_clear()
    get_engine.cache_clear()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    yield get_engine(), config
    get_engine().dispose()
    get_engine.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def session(database):
    with Session(database[0]) as session:
        yield session


@pytest.fixture
def client(database, monkeypatch):
    from app.main import app

    monkeypatch.setattr("app.services.health.check_redis", lambda: True)
    with TestClient(app) as client:
        yield client
