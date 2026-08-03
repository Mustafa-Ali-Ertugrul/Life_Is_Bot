"""Purge service and monthly purge scheduler job tests."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import models  # noqa: F401
from app.core.config import settings
from app.core.database import Base
from app.models import (
    AuditLog,
    BotKey,
    NotificationLog,
    ReminderEvent,
    ReminderStatus,
    StepLog,
    TelegramAccount,
    User,
    UserResponse,
)
from app.scheduler import jobs
from app.services import purge_service

OLD = date(2026, 6, 15)  # before cutoff (2026-07-01) with retention=1
RECENT = date(2026, 8, 10)
FUTURE = date(2026, 9, 5)


async def _seed_user(session: AsyncSession) -> User:
    user = User(name="purge-test", consent_given=True, is_active=True, timezone="Europe/Istanbul")
    session.add(user)
    await session.flush()
    session.add(TelegramAccount(user_id=user.id, telegram_user_id="424242"))
    await session.flush()
    return user


def _event(
    user: User, local_date: date, *, status: str = ReminderStatus.POSITIVE.value
) -> ReminderEvent:
    return ReminderEvent(
        user_id=user.id,
        bot_key=BotKey.HABIT.value,
        related_type="su_ic",
        related_id=None,
        scheduled_at=datetime(local_date.year, local_date.month, local_date.day, 20, tzinfo=UTC),
        scheduled_local_date=local_date,
        dedupe_key=f"purge:{local_date.isoformat()}:{user.id}",
        status=status,
    )


async def test_cutoff_date_for_mid_month() -> None:
    today = date(2026, 8, 31)
    assert purge_service.cutoff_date_for(today, 1) == date(2026, 7, 1)
    assert purge_service.cutoff_date_for(today, 2) == date(2026, 6, 1)
    assert purge_service.cutoff_date_for(today, 0) == date(2026, 8, 1)


async def test_cutoff_date_for_january_boundary() -> None:
    today = date(2026, 1, 15)
    assert purge_service.cutoff_date_for(today, 1) == date(2025, 12, 1)
    assert purge_service.cutoff_date_for(today, 13) == date(2024, 12, 1)


async def test_purge_deletes_old_events_and_dependents(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "data_retention_months", 1)
    user = await _seed_user(db_session)
    old = _event(user, OLD)
    db_session.add(old)
    await db_session.flush()
    db_session.add(
        UserResponse(
            reminder_event_id=old.id,
            user_id=user.id,
            bot_key=BotKey.HABIT.value,
            response="done",
            source="telegram_inline",
            responded_at=datetime(2026, 8, 10, 12, tzinfo=UTC),
        )
    )
    db_session.add(
        NotificationLog(
            reminder_event_id=old.id,
            user_id=user.id,
            sent_at=datetime(2026, 6, 15, 21, tzinfo=UTC),
        )
    )
    await db_session.flush()

    stats = await purge_service.purge_old_data(db_session, date(2026, 8, 31))

    assert stats.reminder_events == 1
    assert stats.user_responses == 1
    assert stats.notification_logs == 1
    assert await db_session.scalar(select(func.count()).select_from(ReminderEvent)) == 0
    assert await db_session.scalar(select(func.count()).select_from(UserResponse)) == 0


async def test_purge_keeps_recent_and_future_events(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "data_retention_months", 1)
    user = await _seed_user(db_session)
    db_session.add_all([_event(user, OLD), _event(user, RECENT), _event(user, FUTURE)])
    await db_session.flush()

    await purge_service.purge_old_data(db_session, date(2026, 8, 31))

    kept = await db_session.scalars(
        select(ReminderEvent.scheduled_local_date).order_by(ReminderEvent.scheduled_local_date)
    )
    assert list(kept) == [RECENT, FUTURE]


async def test_purge_null_event_notification_logs_by_sent_at(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "data_retention_months", 1)
    user = await _seed_user(db_session)
    db_session.add_all(
        [
            NotificationLog(
                reminder_event_id=None,
                user_id=user.id,
                sent_at=datetime(2026, 6, 20, tzinfo=UTC),
            ),
            NotificationLog(
                reminder_event_id=None,
                user_id=user.id,
                sent_at=datetime(2026, 8, 20, tzinfo=UTC),
            ),
        ]
    )
    await db_session.flush()

    await purge_service.purge_old_data(db_session, date(2026, 8, 31))

    remaining = await db_session.scalars(select(NotificationLog.sent_at))
    assert list(remaining) == [datetime(2026, 8, 20)]


async def test_purge_step_logs_by_date(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "data_retention_months", 1)
    user = await _seed_user(db_session)
    db_session.add_all(
        [
            StepLog(user_id=user.id, log_date=OLD, steps=1000),
            StepLog(user_id=user.id, log_date=RECENT, steps=2000),
        ]
    )
    await db_session.flush()

    stats = await purge_service.purge_old_data(db_session, date(2026, 8, 31))

    assert stats.step_logs == 1
    assert await db_session.scalar(select(func.count()).select_from(StepLog)) == 1


async def test_purge_audit_logs_by_created_at(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "data_retention_months", 1)
    user = await _seed_user(db_session)
    db_session.add_all(
        [
            AuditLog(
                user_id=user.id,
                action="x",
                entity_type="y",
                created_at=datetime(2026, 6, 20, tzinfo=UTC),
            ),
            AuditLog(
                user_id=user.id,
                action="x",
                entity_type="y",
                created_at=datetime(2026, 8, 20, tzinfo=UTC),
            ),
        ]
    )
    await db_session.flush()

    stats = await purge_service.purge_old_data(db_session, date(2026, 8, 31))

    assert stats.audit_logs == 1
    assert await db_session.scalar(select(func.count()).select_from(AuditLog)) == 1


async def test_purge_zero_ops_when_no_data(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "data_retention_months", 1)
    stats = await purge_service.purge_old_data(db_session, date(2026, 8, 31))
    assert stats.user_responses == 0
    assert stats.notification_logs == 0
    assert stats.reminder_events == 0


async def test_vacuum_shrinks_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "vacuum.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{src}", connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{src}")
    monkeypatch.setattr(settings, "data_retention_months", 1)

    async with factory() as session:
        user = await _seed_user(session)
        for i in range(3000):
            session.add(
                NotificationLog(
                    reminder_event_id=None,
                    user_id=user.id,
                    message="x" * 400,
                    sent_at=datetime(2026, 6, 1, tzinfo=UTC) + timedelta(minutes=i),
                )
            )
        await session.commit()
        before = src.stat().st_size
        await purge_service.purge_old_data(session, date(2026, 8, 31))
        await session.commit()
    await engine.dispose()

    after = await purge_service.vacuum_database()

    assert after is not None
    assert after < before


async def test_vacuum_skips_non_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "database_url", "postgresql+asyncpg://localhost/db")
    assert await purge_service.vacuum_database() is None


async def test_monthly_purge_job_skips_when_disabled(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "purge_enabled", False)
    user = await _seed_user(db_session)
    db_session.add(_event(user, OLD))
    await db_session.flush()

    await jobs.monthly_purge_job()

    assert await db_session.scalar(select(func.count()).select_from(ReminderEvent)) == 1


async def test_monthly_purge_job_skips_before_last_day(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "purge_enabled", True)
    user = await _seed_user(db_session)
    db_session.add(_event(user, OLD))
    await db_session.flush()
    monkeypatch.setattr(jobs, "now_in", lambda *a: datetime(2026, 8, 15, 23, 55, tzinfo=UTC))

    await jobs.monthly_purge_job()

    assert await db_session.scalar(select(func.count()).select_from(ReminderEvent)) == 1


async def test_monthly_purge_job_runs_on_last_day(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _uow() -> AsyncIterator[AsyncSession]:
        yield db_session

    async def _fake_vacuum() -> int:
        return 42

    monkeypatch.setattr(settings, "purge_enabled", True)
    monkeypatch.setattr(jobs, "unit_of_work", _uow)
    monkeypatch.setattr(jobs, "now_in", lambda *a: datetime(2026, 8, 31, 23, 55, tzinfo=UTC))
    monkeypatch.setattr(purge_service, "vacuum_database", _fake_vacuum)

    user = await _seed_user(db_session)
    db_session.add(_event(user, OLD))
    db_session.add(_event(user, RECENT))
    await db_session.flush()

    await jobs.monthly_purge_job()

    kept = await db_session.scalars(select(ReminderEvent.scheduled_local_date))
    assert list(kept) == [RECENT]
