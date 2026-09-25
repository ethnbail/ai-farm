from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.database.session import get_engine
from app.schemas.dashboard import Health


def check_database() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def check_redis() -> bool:
    try:
        with Redis.from_url(
            get_settings().redis_url.get_secret_value(),
            socket_connect_timeout=1,
            socket_timeout=1,
        ) as client:
            return bool(client.ping())
    except (RedisError, OSError):
        return False


def get_health() -> Health:
    database_ok, redis_ok = check_database(), check_redis()
    return Health(
        status="ok" if database_ok and redis_ok else "degraded",
        database="ok" if database_ok else "unavailable",
        redis="ok" if redis_ok else "unavailable",
    )
