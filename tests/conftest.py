from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.api.main import create_app
from app.models import Base
from app.modules.registry import setup_default_modules

TELEGRAM_USER_ID = "123456789"
TELEGRAM_USER_ID_2 = "987654321"


@asynccontextmanager
async def _session_uow(session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    yield session


@pytest.fixture
def patch_uow(
    monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> Callable[[object], None]:
    def _patch(module: object) -> None:
        monkeypatch.setattr(module, "unit_of_work", lambda: _session_uow(db_session))

    return _patch


@pytest.fixture(autouse=True)
def _default_modules() -> None:
    setup_default_modules()


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
