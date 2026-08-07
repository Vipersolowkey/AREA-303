"""Real orders placed from the storefront cart.

`customer_id` is nullable on purpose: the shop is browsable and buyable without
signing in (see the project's auth scope — only the seller portal requires a
login), so a guest checkout produces an order with no owner. Order history is
the one thing that needs an account, since there's no other way to look it up.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

# pending = created but unpaid. There is no payment gateway wired up, so nothing
# advances past this on its own — a seller moves it along manually.
ORDER_STATUSES = ("pending", "paid", "shipped", "cancelled")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    customer_name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", nullable=False, index=True
    )

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    # Name/brand/price are copied in, not joined: an order must still read
    # correctly after the catalogue is re-priced or a product is renamed.
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str] = mapped_column(String(80), nullable=False)
    unit_price_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
