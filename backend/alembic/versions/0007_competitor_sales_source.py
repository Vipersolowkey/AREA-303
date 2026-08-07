"""competitor_snapshots: sales provenance + widen the GMV column

Two changes, both learned from running the collector against live shops:

1. `sales_source` records where the sales figures came from — a licensed vendor
   feed or a logged-in browser session. An anonymous read can only get
   shop-level fields, so the column is nullable and NULL is the normal case.
   Provenance is per snapshot rather than per competitor because the available
   source changes over the life of a series.

2. `revenue_est_vnd` was int4, whose ceiling is 2,147,483,647 — about 2.1
   billion VND. Estimated cumulative GMV for even a mid-size Shopee shop clears
   that, so the insert would have raised NumericValueOutOfRange. Widened to
   int8. The column has never held a value (the endpoints carrying sales were
   blocked), so there is nothing to migrate.

Revision ID: 0007_competitor_sales_source
Revises: 0006_competitors
Create Date: 2026-08-07 00:00:04.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0007_competitor_sales_source"
down_revision = "0006_competitors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "competitor_snapshots",
        sa.Column("sales_source", sa.String(length=16), nullable=True),
    )
    op.alter_column(
        "competitor_snapshots",
        "revenue_est_vnd",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Narrowing back to int4 would fail on any row above the int4 ceiling, which
    # is precisely the data this migration exists to allow. Clear those rows
    # first so the downgrade is at least deterministic rather than a surprise.
    op.execute(
        "UPDATE competitor_snapshots SET revenue_est_vnd = NULL "
        "WHERE revenue_est_vnd > 2147483647"
    )
    op.alter_column(
        "competitor_snapshots",
        "revenue_est_vnd",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.drop_column("competitor_snapshots", "sales_source")
