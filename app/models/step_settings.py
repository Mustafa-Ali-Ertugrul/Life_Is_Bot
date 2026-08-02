from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class StepSettings(Base, TimestampMixin):
    __tablename__ = "step_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
    )
    daily_target: Mapped[int] = mapped_column(Integer, nullable=False, default=8000)
    reminder_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=21)
    reminder_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    days_of_week: Mapped[str] = mapped_column(String(32), nullable=False, default="1,2,3,4,5,6,7")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped["User"] = relationship(back_populates="step_settings")

    __table_args__ = (
        CheckConstraint(
            "daily_target >= 0 AND daily_target <= 100000",
            name="ck_step_settings_daily_target_range",
        ),
        CheckConstraint(
            "reminder_hour >= 0 AND reminder_hour <= 23",
            name="ck_step_settings_reminder_hour_range",
        ),
        CheckConstraint(
            "reminder_minute >= 0 AND reminder_minute <= 59",
            name="ck_step_settings_reminder_minute_range",
        ),
        Index("ix_step_settings_user_active", "user_id", "is_active"),
    )


__all__ = ["StepSettings"]
