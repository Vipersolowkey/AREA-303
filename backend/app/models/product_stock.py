"""Live stock levels — the DB is the source of truth once a row exists.

The catalogue in :mod:`app.services.commerce_store` is a deterministic seed, so
its `stock` value is a *starting point*, not state: it resets on every process
start and can't record a sale. This table holds the mutable half, lazily seeded
from the catalogue the first time a product is touched.
"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ProductStock(Base, TimestampMixin):
    __tablename__ = "product_stock"

    # The catalogue's slug id is already unique and stable, so it doubles as the
    # primary key — no surrogate needed.
    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
