"""shopee_sessions — a Shopee login each user connects for themselves

Holds Fernet-encrypted Playwright storage_state, one row per user. The plaintext
is a bearer credential for a real Shopee account, so the column is ciphertext and
there is deliberately no index or constraint on it that would leak structure.

No password column exists, and none should be added: the user logs in inside
their own browser and only the resulting cookie jar is uploaded, which is what
keeps 2FA/OTP working.

Revision ID: 0008_shopee_sessions
Revises: 0007_competitor_sales_source
Create Date: 2026-08-07 00:00:05.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_shopee_sessions"
down_revision = "0007_competitor_sales_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shopee_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("state_encrypted", sa.Text(), nullable=False),
        sa.Column("shopee_username", sa.String(length=120), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        # One connection per account: reconnecting replaces the row rather than
        # accumulating stale credentials nobody can tell apart.
        sa.UniqueConstraint("user_id", name="uq_shopee_session_user"),
    )
    op.create_index("ix_shopee_sessions_user_id", "shopee_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_shopee_sessions_user_id", table_name="shopee_sessions")
    op.drop_table("shopee_sessions")
