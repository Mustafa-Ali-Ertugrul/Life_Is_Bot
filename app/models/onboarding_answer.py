from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class OnboardingAnswer(Base, TimestampMixin):
    __tablename__ = "onboarding_answers"
    __table_args__ = (
        UniqueConstraint("user_id", "question_key", name="uq_onboarding_user_question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_key: Mapped[str] = mapped_column(String(30), nullable=False)
    answer_value: Mapped[str] = mapped_column(String(200), nullable=False)

    user: Mapped["User"] = relationship(back_populates="onboarding_answers")


__all__ = ["OnboardingAnswer"]
