from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
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

    async def generate_daily_events_for_all(
        self,
        session: AsyncSession,
        now_utc: datetime | None = None,
    ) -> int:
        """Tüm aktif kullanıcılar için günlük event üretir ve toplam sayıyı döndürür."""
        now = now_utc if now_utc is not None else now_in("UTC")
        result = await session.execute(select(User).where(User.is_active.is_(True)))
        users = list(result.scalars().all())
        created = 0
        for user in users:
            events = await self.generate_daily_events(
                session, EventGenerationContext(user=user, now_utc=now)
            )
            created += len(events)
        return created

    @abstractmethod
    def event_label(self, event: ReminderEvent) -> str | None: ...


__all__ = ["EventGenerationContext", "ReminderModule"]
