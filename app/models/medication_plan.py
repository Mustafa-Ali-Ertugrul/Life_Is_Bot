from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class MedicationPlan(Base, TimestampMixin):
    __tablename__ = "medication_plans"
    __table_args__ = (
        Index("ix_medication_plans_user_active", "user_id", "is_active"),
        CheckConstraint(
            "target_hour BETWEEN 0 AND 23", name="ck_medication_plans_target_hour_range"
        ),
        CheckConstraint(
            "target_minute BETWEEN 0 AND 59", name="ck_medication_plans_target_minute_range"
        ),
        CheckConstraint(
            "with_food IN ('empty', 'full', 'any')", name="ck_medication_plans_with_food"
        ),
        CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR start_date <= end_date",
            name="ck_medication_plans_date_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    dose: Mapped[str | None] = mapped_column(String(80))
    with_food: Mapped[str] = mapped_column(String(16), default="any", nullable=False)
    target_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    target_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    days_of_week: Mapped[str] = mapped_column(String(32), default="1,2,3,4,5,6,7")
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(String(500))

    user: Mapped["User"] = relationship(back_populates="medication_plans")


__all__ = ["MedicationPlan"]
