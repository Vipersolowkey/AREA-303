"""add workspace business profile

Revision ID: 0014_workspace_business_profile
Revises: 0013_merge_marketplace_heads
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_workspace_business_profile"
down_revision = "0013_merge_marketplace_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "seller_workspaces",
        sa.Column("industry", sa.String(40), nullable=False, server_default="fashion"),
    )
    op.add_column("seller_workspaces", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("seller_workspaces", sa.Column("target_customer", sa.Text(), nullable=True))
    op.add_column("seller_workspaces", sa.Column("brand_voice", sa.Text(), nullable=True))
    op.execute(
        "UPDATE seller_workspaces SET "
        "description = 'Shop quần áo và phụ kiện thời trang', "
        "target_customer = 'Khách hàng trẻ yêu thích thời trang ứng dụng', "
        "brand_voice = 'Thân thiện, rõ ràng, tư vấn như stylist' "
        "WHERE description IS NULL"
    )
    op.alter_column("seller_workspaces", "industry", server_default=None)


def downgrade() -> None:
    op.drop_column("seller_workspaces", "brand_voice")
    op.drop_column("seller_workspaces", "target_customer")
    op.drop_column("seller_workspaces", "description")
    op.drop_column("seller_workspaces", "industry")
