from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DatasetType = Literal["products", "orders"]


class ImportMappingRequest(BaseModel):
    mapping: dict[str, str] = Field(min_length=1)


class MarketplaceConnectRequest(BaseModel):
    platform: Literal["shopee", "lazada", "tiktok"]
