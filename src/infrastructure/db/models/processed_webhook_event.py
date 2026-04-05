from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base


class ProcessedWebhookEvent(Base):
    """Stripe webhook `event.id` deduplication (see docs/STRIPE_INTEGRATION_GUIDE.md §2.2)."""

    __tablename__ = "processed_webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(255), unique=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
