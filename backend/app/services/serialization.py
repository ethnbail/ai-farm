"""Public trading records only; exact decimals remain JSON strings."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import inspect


def public(value):
    if isinstance(value, Decimal | UUID):
        return str(value)
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: public(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [public(item) for item in value]
    if hasattr(value, "__table__"):
        return {
            column.key: public(getattr(value, column.key))
            for column in inspect(value).mapper.column_attrs
        }
    return value
