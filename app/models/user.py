from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.bot_preference import BotPreference
    from app.models.habit import Habit
    from app.models.reminder_event import ReminderEvent
    from app.models.telegram_account import TelegramAccount


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("week_start_day BETWEEN 1 AND 7", name="ck_users_week_start_day_range"),
        CheckConstraint(
            "quiet_hours_start IS NULL OR "
            "(length(quiet_hours_start) = 5 AND substr(quiet_hours_start, 3, 1) = ':')",
            name="ck_users_quiet_hours_start_format",
        ),
        CheckConstraint(
            "quiet_hours_end IS NULL OR "
            "(length(quiet_hours_end) = 5 AND substr(quiet_hours_end, 3, 1) = ':')",
            name="ck_users_quiet_hours_end_format",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Istanbul")
    language: Mapped[str] = mapped_column(String(8), default="tr")
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5))
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5))
    week_start_day: Mapped[int] = mapped_column(Integer, default=1)

    telegram_account: Mapped["TelegramAccount | None"] = relationship(
        back_populates="user", uselist=False
    )
    preferences: Mapped[list["BotPreference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reminder_events: Mapped[list["ReminderEvent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    habits: Mapped[list["Habit"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
