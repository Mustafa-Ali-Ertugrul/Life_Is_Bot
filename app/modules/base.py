from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, ReminderEvent, User


@dataclass(frozen=True, slots=True)
class EventGenerationContext:
    user: User
    now_utc: datetime


class ReminderModule(ABC):
    """
    Reminder üretebilen bot modülü.

    Her modül:
    - kendi bot_key'ine sahiptir
    - kendi related_type'ını tanımlar
    - günlük event üretir
    - event label üretir
    """

    bot_key: ClassVar[BotKey]
    related_type: ClassVar[str]
    display_name: ClassVar[str]

    @abstractmethod
    async def generate_daily_events(
        self,
        session: AsyncSession,
        context: EventGenerationContext,
    ) -> Sequence[ReminderEvent]: ...

    @abstractmethod
    def event_label(self, event: ReminderEvent) -> str | None: ...


__all__ = ["EventGenerationContext", "ReminderModule"]
