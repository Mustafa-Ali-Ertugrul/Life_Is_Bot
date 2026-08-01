from __future__ import annotations

import json
from collections.abc import Sequence
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, ReminderEvent
from app.modules.base import EventGenerationContext, ReminderModule
from app.services import supplement_service


class SupplementModule(ReminderModule):
    bot_key: ClassVar[BotKey] = BotKey.SUPPLEMENT
    related_type: ClassVar[str] = "supplement_plan"
    display_name: ClassVar[str] = "Supplement"

    async def generate_daily_events(
        self,
        session: AsyncSession,
        context: EventGenerationContext,
    ) -> Sequence[ReminderEvent]:
        return await supplement_service.generate_today_events(
            session,
            context.user.id,
            now=context.now_utc,
        )

    def event_label(self, event: ReminderEvent) -> str:
        try:
            data = json.loads(event.interpretation_json or "{}")
        except ValueError:
            return "Supplement"
        name = data.get("name")
        if isinstance(name, str) and name:
            return name
        return "Supplement"


__all__ = ["SupplementModule"]
