from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import BotKey

if TYPE_CHECKING:
    from app.models.user import User


class BotPreference(Base, TimestampMixin):
    __tablename__ = "bot_preferences"
    __table_args__ = (UniqueConstraint("user_id", "bot_key", name="uq_bot_preferences_user_bot"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    bot_key: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    settings_json: Mapped[str] = mapped_column(Text, default="{}")

    user: Mapped["User"] = relationship(back_populates="preferences")

    @property
    def bot_key_enum(self) -> BotKey:
        return BotKey(self.bot_key)
