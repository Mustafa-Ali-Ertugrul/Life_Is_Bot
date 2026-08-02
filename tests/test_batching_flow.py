from collections.abc import Sequence
from typing import ClassVar

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, ReminderEvent, ReminderStatus, User
from app.modules.base import EventGenerationContext, ReminderModule
from app.scheduler import jobs
from app.services import preference_service, reminder_service, user_service
from tests.conftest import TELEGRAM_USER_ID, TELEGRAM_USER_ID_2

_generated: list[int] = []


class _HabitFakeModule(ReminderModule):
    bot_key: ClassVar[BotKey] = BotKey.HABIT
    related_type: ClassVar[str] = "test_habit"
    display_name: ClassVar[str] = "Test Habit"

    async def generate_daily_events(
        self,
        session: AsyncSession,
        context: EventGenerationContext,
    ) -> Sequence[ReminderEvent]:
        _generated.append(context.user.id)
        return []

    def event_label(self, event: ReminderEvent) -> str | None:
        return None


class _StepFakeModule(ReminderModule):
    bot_key: ClassVar[BotKey] = BotKey.STEP
    related_type: ClassVar[str] = "test_step"
    display_name: ClassVar[str] = "Test Step"

    async def generate_daily_events(
        self,
        session: AsyncSession,
        context: EventGenerationContext,
    ) -> Sequence[ReminderEvent]:
        _generated.append(context.user.id)
        return []

    def event_label(self, event: ReminderEvent) -> str | None:
        return None


class _AlwaysGenerateModule(_HabitFakeModule):
    async def should_generate(
        self,
        session: AsyncSession,
        context: EventGenerationContext,
    ) -> bool:
        return True


class _CreatingModule(ReminderModule):
    bot_key: ClassVar[BotKey] = BotKey.HABIT
    related_type: ClassVar[str] = "test_creating"
    display_name: ClassVar[str] = "Test Creating"

    async def generate_daily_events(
        self,
        session: AsyncSession,
        context: EventGenerationContext,
    ) -> Sequence[ReminderEvent]:
        return [
            await reminder_service.create_event(
                session,
                user_id=context.user.id,
                bot_key=self.bot_key,
                scheduled_at=context.now_utc,
                related_type=self.related_type,
                related_id=1,
            )
        ]

    def event_label(self, event: ReminderEvent) -> str | None:
        return None


async def _user(db_session: AsyncSession, telegram_id: str = TELEGRAM_USER_ID) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, telegram_id)
    return user.id


@pytest.fixture
def job_patch(monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession) -> None:
    _generated.clear()
    monkeypatch.setattr(jobs, "async_session_factory", lambda: db_session)
    monkeypatch.setattr(jobs, "get_modules", lambda: (_HabitFakeModule(),))


async def test_flow_batched_job_honors_enabled_bots(
    job_patch: None, db_session: AsyncSession
) -> None:
    user_a = await _user(db_session)
    await _user(db_session, TELEGRAM_USER_ID_2)
    await preference_service.toggle_preference(db_session, user_a, BotKey.HABIT, enabled=True)

    await jobs.daily_events_job()

    assert _generated == [user_a]


async def test_flow_batched_job_single_lookup_per_batch(
    monkeypatch: pytest.MonkeyPatch, job_patch: None, db_session: AsyncSession
) -> None:
    user_a = await _user(db_session)
    user_b = await _user(db_session, TELEGRAM_USER_ID_2)
    user_c = await _user(db_session, "555555555")
    await preference_service.toggle_preference(db_session, user_a, BotKey.HABIT, enabled=True)

    lookups: list[list[int]] = []
    real = preference_service.get_enabled_map

    async def _counted(
        session: AsyncSession,
        user_ids: Sequence[int],
        bot_keys: Sequence[BotKey] | None = None,
    ) -> dict[tuple[int, str], bool]:
        lookups.append(list(user_ids))
        return await real(session, user_ids, bot_keys)

    monkeypatch.setattr(preference_service, "get_enabled_map", _counted)

    await jobs.daily_events_job()

    assert len(lookups) == 1
    assert set(lookups[0]) == {user_a, user_b, user_c}
    assert _generated == [user_a]


async def test_flow_batched_job_splits_into_batches(
    monkeypatch: pytest.MonkeyPatch, job_patch: None, db_session: AsyncSession
) -> None:
    user_ids = [await _user(db_session, str(i)) for i in range(1000, 1005)]
    monkeypatch.setattr(jobs, "BATCH_SIZE", 2)

    lookups: list[list[int]] = []
    real = preference_service.get_enabled_map

    async def _counted(
        session: AsyncSession,
        user_ids: Sequence[int],
        bot_keys: Sequence[BotKey] | None = None,
    ) -> dict[tuple[int, str], bool]:
        lookups.append(list(user_ids))
        return await real(session, user_ids, bot_keys)

    monkeypatch.setattr(preference_service, "get_enabled_map", _counted)

    await jobs.daily_events_job()

    assert len(lookups) == 3
    assert [len(batch) for batch in lookups] == [2, 2, 1]
    assert sorted(batch_id for batch in lookups for batch_id in batch) == sorted(user_ids)
    assert _generated == []


async def test_flow_batched_job_skips_inactive_users(
    monkeypatch: pytest.MonkeyPatch, job_patch: None, db_session: AsyncSession
) -> None:
    user_a = await _user(db_session)
    user_b = await _user(db_session, TELEGRAM_USER_ID_2)
    inactive = await db_session.get(User, user_b)
    assert inactive is not None
    inactive.is_active = False
    await db_session.commit()
    await preference_service.toggle_preference(db_session, user_a, BotKey.HABIT, enabled=True)

    lookups: list[list[int]] = []
    real = preference_service.get_enabled_map

    async def _counted(
        session: AsyncSession,
        user_ids: Sequence[int],
        bot_keys: Sequence[BotKey] | None = None,
    ) -> dict[tuple[int, str], bool]:
        lookups.append(list(user_ids))
        return await real(session, user_ids, bot_keys)

    monkeypatch.setattr(preference_service, "get_enabled_map", _counted)

    await jobs.daily_events_job()

    assert lookups == [[user_a]]
    assert _generated == [user_a]


async def test_flow_batched_job_isolates_per_module(
    monkeypatch: pytest.MonkeyPatch, job_patch: None, db_session: AsyncSession
) -> None:
    monkeypatch.setattr(jobs, "get_modules", lambda: (_HabitFakeModule(), _StepFakeModule()))
    user_a = await _user(db_session)
    user_b = await _user(db_session, TELEGRAM_USER_ID_2)
    await preference_service.toggle_preference(db_session, user_a, BotKey.HABIT, enabled=True)
    await preference_service.toggle_preference(db_session, user_b, BotKey.STEP, enabled=True)

    await jobs.daily_events_job()

    assert _generated == [user_a, user_b]


async def test_flow_batched_job_preserves_should_generate_hook(
    monkeypatch: pytest.MonkeyPatch, job_patch: None, db_session: AsyncSession
) -> None:
    monkeypatch.setattr(jobs, "get_modules", lambda: (_AlwaysGenerateModule(),))
    user_a = await _user(db_session)
    user_b = await _user(db_session, TELEGRAM_USER_ID_2)

    await jobs.daily_events_job()

    assert sorted(_generated) == sorted([user_a, user_b])


async def test_flow_batched_job_persists_events(
    monkeypatch: pytest.MonkeyPatch, job_patch: None, db_session: AsyncSession
) -> None:
    monkeypatch.setattr(jobs, "get_modules", lambda: (_CreatingModule(),))
    user_a = await _user(db_session)
    await _user(db_session, TELEGRAM_USER_ID_2)
    await preference_service.toggle_preference(db_session, user_a, BotKey.HABIT, enabled=True)

    await jobs.daily_events_job()

    result = await db_session.execute(select(ReminderEvent))
    events = list(result.scalars().all())
    assert len(events) == 1
    assert events[0].user_id == user_a
    assert events[0].bot_key == BotKey.HABIT.value
    assert events[0].status == ReminderStatus.SCHEDULED.value
