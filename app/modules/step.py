from __future__ import annotations

import json
from collections.abc import Sequence
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, ReminderEvent
from app.modules.base import EventGenerationContext, ReminderModule
from app.services import step_service


class StepModule(ReminderModule):
    bot_key: ClassVar[BotKey] = BotKey.STEP
    related_type: ClassVar[str] = "step_goal"
    display_name: ClassVar[str] = "Adım"

    async def generate_daily_events(
        self,
        session: AsyncSession,
        context: EventGenerationContext,
    ) -> Sequence[ReminderEvent]:
        return await step_service.generate_today_events(
            session,
            context.user.id,
            now=context.now_utc,
        )

    def event_label(self, event: ReminderEvent) -> str:
        try:
            data = json.loads(event.interpretation_json or "{}")
        except ValueError:
            return "Adım hedefi"
        daily_target = data.get("daily_target")
        if isinstance(daily_target, int) and daily_target > 0:
            return f"Adım hedefi: {daily_target}"
        return "Adım hedefi"


__all__ = ["StepModule"]
