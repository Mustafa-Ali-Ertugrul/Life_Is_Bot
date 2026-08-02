from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class StepLog(Base, TimestampMixin):
    __tablename__ = "step_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    steps: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")

    user: Mapped["User"] = relationship(back_populates="step_logs")

    __table_args__ = (
        UniqueConstraint("user_id", "log_date", name="uq_step_logs_user_date"),
        CheckConstraint(
            "steps >= 0 AND steps <= 200000",
            name="ck_step_logs_steps_range",
        ),
        Index("ix_step_logs_user_date", "user_id", "log_date"),
    )


__all__ = ["StepLog"]
