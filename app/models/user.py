from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.bot_preference import BotPreference
    from app.models.telegram_account import TelegramAccount


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Istanbul")
    language: Mapped[str] = mapped_column(String(8), default="tr")
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    telegram_account: Mapped["TelegramAccount | None"] = relationship(
        back_populates="user", uselist=False
    )
    preferences: Mapped[list["BotPreference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
