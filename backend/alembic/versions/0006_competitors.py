"""tracked_competitors, competitor_snapshots

Revision ID: 0006_competitors
Revises: 0005_orders_stock
Create Date: 2026-08-07 00:00:03.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_competitors"
down_revision = "0005_orders_stock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tracked_competitors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("shop_ref", sa.String(length=128), nullable=False),
        sa.Column("shop_id", sa.String(length=64), nullable=True),
        sa.Column("shop_slug", sa.String(length=128), nullable=True),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("added_by", sa.String(length=64), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("platform", "shop_ref", name="uq_competitor_ref"),
    )
    op.create_index("ix_tracked_competitors_platform", "tracked_competitors", ["platform"])
    op.create_index("ix_tracked_competitors_shop_ref", "tracked_competitors", ["shop_ref"])

    op.create_table(
        "competitor_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("competitor_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("follower_count", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("product_count", sa.Integer(), nullable=True),
        sa.Column("items_sold_total", sa.Integer(), nullable=True),
        sa.Column("revenue_est_vnd", sa.Integer(), nullable=True),
        sa.Column("voucher_count", sa.Integer(), nullable=True),
        sa.Column("top_products", postgresql.JSONB(), nullable=True),
        sa.Column("promotions", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["competitor_id"], ["tracked_competitors.id"],
                                ondelete="CASCADE"),
    )
    op.create_index("ix_competitor_snapshots_competitor_id", "competitor_snapshots",
                    ["competitor_id"])
    op.create_index("ix_competitor_snapshots_captured_at", "competitor_snapshots",
                    ["captured_at"])


def downgrade() -> None:
    op.drop_index("ix_competitor_snapshots_captured_at", table_name="competitor_snapshots")
    op.drop_index("ix_competitor_snapshots_competitor_id", table_name="competitor_snapshots")
    op.drop_table("competitor_snapshots")
    op.drop_index("ix_tracked_competitors_shop_ref", table_name="tracked_competitors")
    op.drop_index("ix_tracked_competitors_platform", table_name="tracked_competitors")
    op.drop_table("tracked_competitors")
