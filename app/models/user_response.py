from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserResponse(Base):
    __tablename__ = "user_responses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reminder_event_id: Mapped[int] = mapped_column(ForeignKey("reminder_events.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    bot_key: Mapped[str] = mapped_column(String(32), nullable=False)
    response: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="telegram_inline")
    responded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
