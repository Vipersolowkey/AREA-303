"""stage and commit real workspace onboarding data

Revision ID: 0015_workspace_onboarding_data
Revises: 0014_workspace_business_profile
"""

import sqlalchemy as sa

from alembic import op

revision = "0015_workspace_onboarding_data"
down_revision = "0014_workspace_business_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_data_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("dataset_type", sa.String(length=16), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_kind", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("mapping", sa.JSON(), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["seller_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_workspace_data_imports_workspace_id", "workspace_data_imports", ["workspace_id"])
    op.create_table(
        "workspace_data_import_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_values", sa.JSON(), nullable=False),
        sa.Column("normalized_values", sa.JSON(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["import_id"], ["workspace_data_imports.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("import_id", "row_number", name="uq_import_row_number"),
    )
    op.create_index("ix_workspace_data_import_rows_import_id", "workspace_data_import_rows", ["import_id"])
    op.create_table(
        "workspace_data_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("dataset_type", sa.String(length=16), nullable=False),
        sa.Column("external_key", sa.String(length=160), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["seller_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["import_id"], ["workspace_data_imports.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("workspace_id", "dataset_type", "external_key", name="uq_workspace_data_record"),
    )
    op.create_index("ix_workspace_data_records_workspace_id", "workspace_data_records", ["workspace_id"])
    op.create_table(
        "workspace_marketplace_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("seller_account_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["seller_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_account_id"], ["seller_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", name="uq_workspace_marketplace_account_workspace"),
        sa.UniqueConstraint("seller_account_id", name="uq_workspace_marketplace_account_seller"),
    )


def downgrade() -> None:
    op.drop_table("workspace_marketplace_accounts")
    op.drop_index("ix_workspace_data_records_workspace_id", table_name="workspace_data_records")
    op.drop_table("workspace_data_records")
    op.drop_index("ix_workspace_data_import_rows_import_id", table_name="workspace_data_import_rows")
    op.drop_table("workspace_data_import_rows")
    op.drop_index("ix_workspace_data_imports_workspace_id", table_name="workspace_data_imports")
    op.drop_table("workspace_data_imports")
