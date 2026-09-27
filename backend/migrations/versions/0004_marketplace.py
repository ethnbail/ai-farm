"""Extend existing Marketplace records; preserve all Phase 1–4 accounts and evidence."""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def record_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def listing_column(index=False, unique=False):
    return sa.Column(
        "listing_id",
        sa.Uuid(),
        sa.ForeignKey("marketplace_listings.id"),
        nullable=False,
        index=index,
        unique=unique,
    )


def upgrade():
    with op.batch_alter_table("marketplace_listings") as batch:
        for name in [
            "first_seen_at",
            "last_seen_at",
            "updated_at",
            "listed_at",
            "first_known_post",
        ]:
            batch.add_column(sa.Column(name, sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="NEW"))
        batch.add_column(
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.add_column(
            sa.Column("repost_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("repost_probability", sa.Numeric(6, 4), nullable=True))
        batch.add_column(sa.Column("duplicate_of_listing_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_marketplace_listings_duplicate_of_listing_id_marketplace_listings"),
            "marketplace_listings",
            ["duplicate_of_listing_id"],
            ["id"],
        )
    op.execute(
        "UPDATE marketplace_listings SET first_seen_at=created_at, "
        "last_seen_at=created_at, updated_at=created_at, "
        "first_known_post=created_at"
    )
    op.create_table(
        "marketplace_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("preferences", sa.JSON(), nullable=False),
    )
    op.bulk_insert(
        sa.table(
            "marketplace_settings",
            sa.column("id", sa.Integer()),
            sa.column("preferences", sa.JSON()),
        ),
        [{"id": 1, "preferences": {}}],
    )
    op.create_table(
        "marketplace_price_history",
        *record_columns(),
        listing_column(index=True),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    existing = sa.table(
        "marketplace_listings",
        sa.column("id", sa.Uuid()),
        sa.column("asking_price", sa.Numeric(18, 2)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    history = sa.table(
        "marketplace_price_history",
        sa.column("id", sa.Uuid()),
        sa.column("listing_id", sa.Uuid()),
        sa.column("price", sa.Numeric(18, 2)),
        sa.column("observed_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    for row in op.get_bind().execute(sa.select(existing)).mappings():
        op.bulk_insert(
            history,
            [
                {
                    "id": uuid4(),
                    "listing_id": row["id"],
                    "price": row["asking_price"],
                    "observed_at": row["created_at"],
                    "created_at": row["created_at"],
                }
            ],
        )
    op.create_table(
        "marketplace_duplicate_matches",
        *record_columns(),
        listing_column(),
        sa.Column(
            "candidate_id", sa.Uuid(), sa.ForeignKey("marketplace_listings.id"), nullable=False
        ),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.UniqueConstraint("listing_id", "candidate_id"),
    )
    op.create_table(
        "marketplace_seller_profiles",
        *record_columns(),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("source_seller_id", sa.String(100), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.UniqueConstraint("source", "source_seller_id"),
    )
    for name in ["marketplace_comparables", "marketplace_demand_snapshots"]:
        op.create_table(
            name,
            *record_columns(),
            listing_column(index=True),
            sa.Column("evidence", sa.JSON(), nullable=False),
        )
    op.create_table(
        "marketplace_inventory",
        *record_columns(),
        listing_column(unique=True),
        sa.Column("purchase", sa.JSON(), nullable=False),
        sa.Column("sold", sa.Boolean(), nullable=False),
        sa.Column("aging_bucket", sa.String(30), nullable=False),
    )
    op.create_table(
        "marketplace_calibration",
        *record_columns(),
        listing_column(),
        sa.Column("hypothetical", sa.Boolean(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.UniqueConstraint("listing_id", "hypothetical"),
    )
    op.create_table(
        "marketplace_notifications",
        *record_columns(),
        listing_column(index=True),
        sa.Column("severity", sa.String(12), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("dedup_key", sa.String(100), nullable=False, unique=True),
        sa.Column("message", sa.String(500), nullable=False),
    )


def downgrade():
    for name in [
        "marketplace_notifications",
        "marketplace_calibration",
        "marketplace_inventory",
        "marketplace_demand_snapshots",
        "marketplace_comparables",
        "marketplace_seller_profiles",
        "marketplace_duplicate_matches",
        "marketplace_price_history",
        "marketplace_settings",
    ]:
        op.drop_table(name)
    with op.batch_alter_table("marketplace_listings") as batch:
        batch.drop_constraint(
            op.f("fk_marketplace_listings_duplicate_of_listing_id_marketplace_listings"),
            type_="foreignkey",
        )
        for name in [
            "first_seen_at",
            "last_seen_at",
            "updated_at",
            "listed_at",
            "first_known_post",
            "status",
            "active",
            "repost_count",
            "repost_probability",
            "duplicate_of_listing_id",
        ]:
            batch.drop_column(name)
