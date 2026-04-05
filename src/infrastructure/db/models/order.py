from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.checkout_statuses import OrderStatus
from src.infrastructure.db.base import Base

if TYPE_CHECKING:
    from src.infrastructure.db.models.order_item import OrderItem
    from src.infrastructure.db.models.payment import Payment
    from src.infrastructure.db.models.user import User


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=OrderStatus.PENDING.value,
        server_default=OrderStatus.PENDING.value,
        index=True,
    )
    total_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    payment: Mapped[Payment | None] = relationship(
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan",
    )
