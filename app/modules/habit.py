from __future__ import annotations

import json
from collections.abc import Sequence
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, ReminderEvent
from app.modules.base import EventGenerationContext, ReminderModule
from app.services import habit_service


class HabitModule(ReminderModule):
    bot_key: ClassVar[BotKey] = BotKey.HABIT
    related_type: ClassVar[str] = "habit"
    display_name: ClassVar[str] = "Genel Rutin"

    async def generate_daily_events(
        self,
        session: AsyncSession,
        context: EventGenerationContext,
    ) -> Sequence[ReminderEvent]:
        return await habit_service.generate_today_events(
            session,
            context.user.id,
            now=context.now_utc,
        )

    def event_label(self, event: ReminderEvent) -> str | None:
        try:
            data = json.loads(event.interpretation_json or "{}")
        except ValueError:
            return None
        name = data.get("habit_name")
        if isinstance(name, str) and name:
            return name
        return None


__all__ = ["HabitModule"]
