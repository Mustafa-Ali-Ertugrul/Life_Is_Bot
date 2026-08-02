from __future__ import annotations

import json
from collections.abc import Sequence
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, ReminderEvent
from app.modules.base import EventGenerationContext, ReminderModule
from app.services import medication_service


class MedicationModule(ReminderModule):
    bot_key: ClassVar[BotKey] = BotKey.MEDICATION
    related_type: ClassVar[str] = "medication_plan"
    display_name: ClassVar[str] = "İlaç"

    async def generate_daily_events(
        self,
        session: AsyncSession,
        context: EventGenerationContext,
    ) -> Sequence[ReminderEvent]:
        return await medication_service.generate_today_events(
            session,
            context.user.id,
            now=context.now_utc,
        )

    def event_label(self, event: ReminderEvent) -> str:
        try:
            data = json.loads(event.interpretation_json or "{}")
        except ValueError:
            return "İlaç"
        name = data.get("name")
        dose = data.get("dose")
        if isinstance(name, str) and name:
            if isinstance(dose, str) and dose:
                return f"{name} ({dose})"
            return name
        return "İlaç"


__all__ = ["MedicationModule"]
