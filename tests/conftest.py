from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import create_access_token
from app.api.deps import get_db
from app.api.main import create_app
from app.models import Base, TelegramAccount, User
from app.modules.registry import setup_default_modules

TELEGRAM_USER_ID = "123456789"
TELEGRAM_USER_ID_2 = "987654321"

TEST_JWT_SECRET = "test-jwt-secret-0123456789abcdef0123456789abcdef"
TEST_API_KEY = "test-api-key"
TEST_TELEGRAM_USER_ID = 777000


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


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Isolate the in-memory rate limiter counters between tests."""
    from app.api.rate_limit import limiter

    limiter.reset()


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
async def api_app(db_session: AsyncSession) -> FastAPI:
    app = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    return app


@pytest_asyncio.fixture
async def api_client(api_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def api_user(db_session: AsyncSession) -> User:
    user = User(name="api-test", consent_given=True, is_active=True)
    db_session.add(user)
    await db_session.flush()
    db_session.add(TelegramAccount(user_id=user.id, telegram_user_id=str(TEST_TELEGRAM_USER_ID)))
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def auth_headers(monkeypatch: pytest.MonkeyPatch, api_user: User) -> dict[str, str]:
    monkeypatch.setattr("app.api.auth.settings.jwt_secret", TEST_JWT_SECRET)
    return {"Authorization": f"Bearer {create_access_token(api_user.id)}"}


@pytest_asyncio.fixture
async def api_user_2(db_session: AsyncSession) -> User:
    user = User(name="api-test-2", consent_given=True, is_active=True)
    db_session.add(user)
    await db_session.flush()
    db_session.add(TelegramAccount(user_id=user.id, telegram_user_id=str(TELEGRAM_USER_ID_2)))
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def auth_headers_user2(monkeypatch: pytest.MonkeyPatch, api_user_2: User) -> dict[str, str]:
    monkeypatch.setattr("app.api.auth.settings.jwt_secret", TEST_JWT_SECRET)
    return {"Authorization": f"Bearer {create_access_token(api_user_2.id)}"}
