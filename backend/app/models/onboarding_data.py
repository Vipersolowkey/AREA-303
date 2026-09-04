"""Persisted, workspace-scoped onboarding imports.

Uploads are staged first.  The original tabular values, mapping, validation
errors and final records are deliberately separate so pressing "import" can
never write partly-validated business data.
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WorkspaceDataImport(Base, TimestampMixin):
    __tablename__ = "workspace_data_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("seller_workspaces.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    dataset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    headers: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    mapping: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WorkspaceDataImportRow(Base):
    __tablename__ = "workspace_data_import_rows"
    __table_args__ = (UniqueConstraint("import_id", "row_number", name="uq_import_row_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_data_imports.id", ondelete="CASCADE"), index=True, nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_values: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    normalized_values: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    errors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class WorkspaceDataRecord(Base, TimestampMixin):
    """A real, accepted product or order record from a confirmed import."""

    __tablename__ = "workspace_data_records"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "dataset_type", "external_key", name="uq_workspace_data_record"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("seller_workspaces.id", ondelete="CASCADE"), index=True, nullable=False
    )
    import_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_data_imports.id", ondelete="RESTRICT"), nullable=False
    )
    dataset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    external_key: Mapped[str] = mapped_column(String(160), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class WorkspaceMarketplaceAccount(Base, TimestampMixin):
    """Connects a workspace to the existing credential-safe OAuth account."""

    __tablename__ = "workspace_marketplace_accounts"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_workspace_marketplace_account_workspace"),
        UniqueConstraint("seller_account_id", name="uq_workspace_marketplace_account_seller"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("seller_workspaces.id", ondelete="CASCADE"), nullable=False
    )
    seller_account_id: Mapped[int] = mapped_column(
        ForeignKey("seller_accounts.id", ondelete="CASCADE"), nullable=False
    )
