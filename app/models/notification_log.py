from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    __table_args__ = (
        Index("ix_notification_logs_user_sent", "user_id", "sent_at"),
        Index("ix_notification_logs_reminder_event", "reminder_event_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reminder_event_id: Mapped[int | None] = mapped_column(ForeignKey("reminder_events.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), default="telegram")
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(32))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
