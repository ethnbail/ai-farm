"""Initial Phase 1 schema.

Revision ID: 0001
Revises: None
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("agent_type", sa.String(30), nullable=False),
        sa.Column("starting_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("current_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.CheckConstraint("starting_balance > 0", name="positive_starting_balance"),
        sa.CheckConstraint("agent_type IN ('equities', 'options')", name="agent_type"),
        sa.CheckConstraint("status IN ('idle', 'running', 'paused', 'error')", name="status"),
    )
    op.create_table(
        "trades",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("asset_type", sa.String(30), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("stop_loss", sa.Numeric(18, 4), nullable=True),
        sa.Column("take_profit", sa.Numeric(18, 4), nullable=True),
        sa.Column("exit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(18, 2), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.CheckConstraint("quantity > 0", name="positive_quantity"),
        sa.CheckConstraint("entry_price >= 0", name="nonnegative_entry_price"),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="side"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="status"),
    )
    op.create_index("ix_trades_agent_id", "trades", ["agent_id"])
    op.create_table(
        "marketplace_opportunities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_listing_id", sa.String(200), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("asking_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("expected_resale_low", sa.Numeric(18, 2), nullable=True),
        sa.Column("expected_resale_high", sa.Numeric(18, 2), nullable=True),
        sa.Column("expected_profit", sa.Numeric(18, 2), nullable=True),
        sa.Column("listing_url", sa.Text(), nullable=True),
        sa.Column("zip_code", sa.String(10), nullable=True),
        sa.Column("distance_miles", sa.Numeric(10, 2), nullable=True),
        sa.Column("listing_age_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("asking_price >= 0", name="nonnegative_asking_price"),
    )
    op.create_table(
        "system_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_events_event_type", "system_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_system_events_event_type", table_name="system_events")
    op.drop_table("system_events")
    op.drop_table("marketplace_opportunities")
    op.drop_index("ix_trades_agent_id", table_name="trades")
    op.drop_table("trades")
    op.drop_table("agents")
