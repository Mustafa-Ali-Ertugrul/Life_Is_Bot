from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class SportPlan(Base, TimestampMixin):
    __tablename__ = "sport_plans"
    __table_args__ = (
        Index("ix_sport_plans_user_active", "user_id", "is_active"),
        CheckConstraint("target_hour BETWEEN 0 AND 23", name="ck_sport_plans_target_hour_range"),
        CheckConstraint(
            "target_minute BETWEEN 0 AND 59", name="ck_sport_plans_target_minute_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    sport_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    target_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    days_of_week: Mapped[str] = mapped_column(String(32), default="1,2,3,4,5")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="sport_plans")


__all__ = ["SportPlan"]
