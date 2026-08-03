import hashlib
import hmac
import json
import time
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import asynccontextmanager
from urllib.parse import urlencode

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.api.main import create_app
from app.models import Base, TelegramAccount, User
from app.modules.registry import setup_default_modules

TELEGRAM_USER_ID = "123456789"
TELEGRAM_USER_ID_2 = "987654321"

TEST_BOT_TOKEN = "123456:TEST-TOKEN"
TEST_API_KEY = "test-api-key"
TEST_TELEGRAM_USER_ID = 777000


def make_init_data(telegram_user_id: int | None = None, *, auth_date: int | None = None) -> str:
    """Build a signed Telegram WebApp initData query string for tests."""
    params: dict[str, str] = {}
    if telegram_user_id is not None:
        user = json.dumps({"id": telegram_user_id, "first_name": "Test"}, separators=(",", ":"))
        params["user"] = user
    params["auth_date"] = str(auth_date if auth_date is not None else int(time.time()))
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", TEST_BOT_TOKEN.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(params)


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
    monkeypatch.setattr("app.api.auth.settings.bot_token", TEST_BOT_TOKEN)
    return {"Authorization": f"Bearer {make_init_data(TEST_TELEGRAM_USER_ID)}"}


@pytest_asyncio.fixture
async def api_key_headers(monkeypatch: pytest.MonkeyPatch, api_user: User) -> dict[str, str]:
    monkeypatch.setattr("app.api.auth.settings.api_key", TEST_API_KEY)
    return {"X-API-Key": TEST_API_KEY}
