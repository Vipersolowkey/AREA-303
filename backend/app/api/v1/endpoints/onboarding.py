"""Real-data gate for seller workspace onboarding."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    WorkspaceAccess,
    get_current_user,
    get_db_dep,
    get_workspace_access,
    require_workspace_role,
)
from app.core.exceptions import ValidationError
from app.core.responses import ApiResponse, PageMeta
from app.schemas.onboarding import ImportMappingRequest, MarketplaceConnectRequest
from app.services import onboarding_data, workspace_service

router = APIRouter()
_EDITOR = require_workspace_role("owner", "manager")


def _ok(data: object) -> ApiResponse:
    return ApiResponse(success=True, data=data, meta=PageMeta(), error=None)


def _batch_out(batch, rows=None) -> dict:  # noqa: ANN001
    return {
        "id": batch.id,
        "dataset_type": batch.dataset_type,
        "filename": batch.filename,
        "file_kind": batch.file_kind,
        "status": batch.status,
        "headers": batch.headers,
        "mapping": batch.mapping,
        "total_rows": batch.total_rows,
        "valid_rows": batch.valid_rows,
        "invalid_rows": batch.invalid_rows,
        "rows": [
            {"row_number": row.row_number, "raw_values": row.raw_values,
             "normalized_values": row.normalized_values, "errors": row.errors,
             "is_valid": row.is_valid}
            for row in (rows or [])
        ],
    }


@router.get("/readiness", response_model=ApiResponse[dict])
async def get_readiness(access: WorkspaceAccess = Depends(get_workspace_access), db: AsyncSession = Depends(get_db_dep)) -> ApiResponse:
    return _ok(await onboarding_data.readiness(db, access.workspace_id))


@router.get("/readiness/{workspace_id}", response_model=ApiResponse[dict])
async def get_workspace_readiness(
    workspace_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_dep),
) -> ApiResponse:
    # This is intentionally path-scoped rather than depending on the active
    # cookie/header: the onboarding list must show which of several workspaces
    # can be entered without temporarily switching tenants in the browser.
    await workspace_service.get_accessible_workspace(
        db, workspace_id=workspace_id, user_id=int(user["sub"]),
        is_platform_admin=user.get("role") == "admin",
    )
    return _ok(await onboarding_data.readiness(db, workspace_id))


@router.get("/products", response_model=ApiResponse[list[dict]])
async def workspace_products(
    access: WorkspaceAccess = Depends(get_workspace_access),
    db: AsyncSession = Depends(get_db_dep),
) -> ApiResponse:
    return _ok(await onboarding_data.list_workspace_products(db, access.workspace_id))


@router.post("/imports/preview", response_model=ApiResponse[dict])
async def preview_import(
    dataset_type: str = Form(...),
    file: UploadFile = File(...),
    access: WorkspaceAccess = Depends(_EDITOR),
    db: AsyncSession = Depends(get_db_dep),
) -> ApiResponse:
    if not file.filename:
        raise ValidationError("Chưa chọn tệp để import.")
    content = await file.read()
    batch = await onboarding_data.create_preview(
        db, workspace_id=access.workspace_id, user_id=access.user_id,
        dataset_type=dataset_type, filename=file.filename, content=content,
    )
    rows = await onboarding_data.list_rows(db, batch.id)
    return _ok(_batch_out(batch, rows[:20]))


@router.post("/imports/{import_id}/validate", response_model=ApiResponse[dict])
async def validate_import(
    import_id: int,
    req: ImportMappingRequest,
    access: WorkspaceAccess = Depends(_EDITOR),
    db: AsyncSession = Depends(get_db_dep),
) -> ApiResponse:
    batch = await onboarding_data.get_import(db, workspace_id=access.workspace_id, import_id=import_id)
    rows = await onboarding_data.validate_import(db, batch=batch, mapping=req.mapping)
    await db.refresh(batch)
    return _ok(_batch_out(batch, rows))


@router.post("/imports/{import_id}/confirm", response_model=ApiResponse[dict])
async def confirm_import(
    import_id: int,
    access: WorkspaceAccess = Depends(_EDITOR),
    db: AsyncSession = Depends(get_db_dep),
) -> ApiResponse:
    batch = await onboarding_data.get_import(db, workspace_id=access.workspace_id, import_id=import_id)
    written = await onboarding_data.confirm_import(db, batch=batch)
    return _ok({"import_id": import_id, "written_rows": written, "readiness": await onboarding_data.readiness(db, access.workspace_id)})


@router.post("/marketplace/connect", response_model=ApiResponse[dict])
async def connect_marketplace(
    req: MarketplaceConnectRequest,
    access: WorkspaceAccess = Depends(_EDITOR),
    db: AsyncSession = Depends(get_db_dep),
) -> ApiResponse:
    url = await onboarding_data.begin_marketplace_connection(
        db, workspace_id=access.workspace_id, user_id=access.user_id,
        workspace_name=access.workspace.name, platform=req.platform,
    )
    return _ok({"authorize_url": url})
