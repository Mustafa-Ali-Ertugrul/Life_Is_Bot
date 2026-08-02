from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import database
from app.models import Base, User


class _MarkerError(RuntimeError):
    pass


@pytest_asyncio.fixture
async def uow_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(database, "async_session_factory", factory)
    yield factory

    await engine.dispose()


async def _count_users(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        result = await session.execute(select(User))
        return len(list(result.scalars().all()))


async def test_unit_of_work_commits_on_success(
    uow_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with database.unit_of_work() as session:
        session.add(User(name="test", consent_given=True, is_active=True))

    assert await _count_users(uow_factory) == 1


async def test_unit_of_work_rolls_back_on_error(
    uow_factory: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(_MarkerError):
        async with database.unit_of_work() as session:
            session.add(User(name="test", consent_given=True, is_active=True))
            raise _MarkerError("boom")

    assert await _count_users(uow_factory) == 0


async def test_unit_of_work_atomic_across_services(
    uow_factory: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(_MarkerError):
        async with database.unit_of_work() as session:
            session.add(User(name="first", consent_given=True, is_active=True))
            await session.flush()
            session.add(User(name="second", consent_given=True, is_active=True))
            raise _MarkerError("boom")

    assert await _count_users(uow_factory) == 0


async def test_unit_of_work_propagates_exception(
    uow_factory: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(_MarkerError) as exc_info:
        async with database.unit_of_work():
            raise _MarkerError("boom")

    assert exc_info.value.args == ("boom",)
