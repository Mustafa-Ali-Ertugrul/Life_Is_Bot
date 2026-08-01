from __future__ import annotations

import json
from collections.abc import Sequence
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, ReminderEvent
from app.modules.base import EventGenerationContext, ReminderModule
from app.services import sport_service


class SportModule(ReminderModule):
    bot_key: ClassVar[BotKey] = BotKey.SPORT
    related_type: ClassVar[str] = "sport_plan"
    display_name: ClassVar[str] = "Spor"

    async def generate_daily_events(
        self,
        session: AsyncSession,
        context: EventGenerationContext,
    ) -> Sequence[ReminderEvent]:
        return await sport_service.generate_today_events(
            session,
            context.user.id,
            now=context.now_utc,
        )

    def event_label(self, event: ReminderEvent) -> str | None:
        try:
            data = json.loads(event.interpretation_json or "{}")
        except ValueError:
            return None
        sport_type = data.get("sport_type")
        if isinstance(sport_type, str) and sport_type:
            return f"{sport_type.capitalize()} antrenmanı"
        return None


__all__ = ["SportModule"]
