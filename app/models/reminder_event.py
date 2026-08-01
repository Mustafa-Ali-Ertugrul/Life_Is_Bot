from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ReminderEvent(Base):
    __tablename__ = "reminder_events"
    __table_args__ = (
        Index("ix_reminder_events_user_status", "user_id", "status"),
        Index("ix_reminder_events_scheduled_at", "scheduled_at"),
        Index("ix_reminder_events_related", "related_type", "related_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    bot_key: Mapped[str] = mapped_column(String(32), nullable=False)
    related_type: Mapped[str | None] = mapped_column(String(64))
    related_id: Mapped[int | None] = mapped_column(Integer)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    interpretation_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="reminder_events")
