"""Webhook endpoint and lifespan tests."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from telegram import Update

from app.api.main import lifespan

MESSAGE_PAYLOAD = {
    "update_id": 100,
    "message": {
        "message_id": 10,
        "date": 1700000000,
        "chat": {"id": 12345, "type": "private", "first_name": "T"},
        "from": {"id": 12345, "is_bot": False, "first_name": "T"},
        "text": "/start",
    },
}

CALLBACK_PAYLOAD = {
    "update_id": 101,
    "callback_query": {
        "id": "cb-1",
        "from": {"id": 12345, "is_bot": False, "first_name": "T"},
        "chat_instance": "123",
        "data": "ui:menu:main:1",
        "message": {
            "message_id": 11,
            "date": 1700000000,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 12345, "is_bot": False, "first_name": "T"},
        },
    },
}


async def test_webhook_valid_update_returns_ok(
    api_client: AsyncClient, api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.routers.webhook.settings.telegram_webhook_secret", "webhook-secret"
    )
    api_app.state.bot_application = AsyncMock()
    api_app.state.bot_application.bot.defaults = None

    response = await api_client.post(
        "/api/webhook/telegram",
        json=MESSAGE_PAYLOAD,
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


async def test_webhook_wrong_secret_returns_403(
    api_client: AsyncClient, api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.routers.webhook.settings.telegram_webhook_secret", "webhook-secret"
    )
    api_app.state.bot_application = AsyncMock()
    api_app.state.bot_application.bot.defaults = None

    response = await api_client.post(
        "/api/webhook/telegram",
        json=MESSAGE_PAYLOAD,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )

    assert response.status_code == 403


async def test_webhook_missing_secret_returns_403(
    api_client: AsyncClient, api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.routers.webhook.settings.telegram_webhook_secret", "webhook-secret"
    )
    api_app.state.bot_application = AsyncMock()
    api_app.state.bot_application.bot.defaults = None

    response = await api_client.post("/api/webhook/telegram", json=MESSAGE_PAYLOAD)

    assert response.status_code == 403


async def test_webhook_empty_secret_skips_check(
    api_client: AsyncClient, api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.routers.webhook.settings.telegram_webhook_secret", "")
    api_app.state.bot_application = AsyncMock()
    api_app.state.bot_application.bot.defaults = None

    response = await api_client.post("/api/webhook/telegram", json=MESSAGE_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {"ok": True}


async def test_webhook_invalid_json_returns_400(
    api_client: AsyncClient, api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.routers.webhook.settings.telegram_webhook_secret", "")
    api_app.state.bot_application = AsyncMock()
    api_app.state.bot_application.bot.defaults = None

    response = await api_client.post(
        "/api/webhook/telegram",
        content="not-json",
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )

    assert response.status_code == 400


async def test_webhook_disabled_returns_503(api_client: AsyncClient) -> None:
    response = await api_client.post("/api/webhook/telegram", json=MESSAGE_PAYLOAD)

    assert response.status_code == 503


async def test_webhook_process_update_called(
    api_client: AsyncClient, api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.routers.webhook.settings.telegram_webhook_secret", "webhook-secret"
    )
    bot_application = AsyncMock()
    bot_application.bot.defaults = None
    api_app.state.bot_application = bot_application

    await api_client.post(
        "/api/webhook/telegram",
        json=MESSAGE_PAYLOAD,
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )

    bot_application.process_update.assert_awaited_once()
    update = bot_application.process_update.await_args.args[0]
    assert isinstance(update, Update)
    assert update.update_id == 100


async def test_webhook_message_update_parses_text(
    api_client: AsyncClient, api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.routers.webhook.settings.telegram_webhook_secret", "webhook-secret"
    )
    bot_application = AsyncMock()
    bot_application.bot.defaults = None
    api_app.state.bot_application = bot_application

    await api_client.post(
        "/api/webhook/telegram",
        json=MESSAGE_PAYLOAD,
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )

    update = bot_application.process_update.await_args.args[0]
    assert update.message is not None
    assert update.message.text == "/start"


async def test_webhook_callback_update_parses_data(
    api_client: AsyncClient, api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.routers.webhook.settings.telegram_webhook_secret", "webhook-secret"
    )
    bot_application = AsyncMock()
    bot_application.bot.defaults = None
    api_app.state.bot_application = bot_application

    await api_client.post(
        "/api/webhook/telegram",
        json=CALLBACK_PAYLOAD,
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )

    update = bot_application.process_update.await_args.args[0]
    assert update.callback_query is not None
    assert update.callback_query.data == "ui:menu:main:1"


async def test_lifespan_webhook_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.main.settings.webhook_mode", True)
    monkeypatch.setattr(
        "app.api.main.settings.telegram_webhook_url", "https://example.com/telegram"
    )
    monkeypatch.setattr("app.api.main.settings.telegram_webhook_secret", "webhook-secret")
    bot_application = AsyncMock()
    monkeypatch.setattr("app.api.main.build_application", lambda: bot_application)

    app = FastAPI()
    async with lifespan(app):
        assert app.state.bot_application is bot_application
        bot_application.initialize.assert_awaited_once()
        bot_application.start.assert_awaited_once()
        bot_application.bot.set_webhook.assert_awaited_once_with(
            url="https://example.com/telegram",
            secret_token="webhook-secret",
            allowed_updates=["message", "callback_query"],
        )


async def test_lifespan_webhook_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.main.settings.webhook_mode", True)
    monkeypatch.setattr(
        "app.api.main.settings.telegram_webhook_url", "https://example.com/telegram"
    )
    monkeypatch.setattr("app.api.main.settings.telegram_webhook_secret", "webhook-secret")
    bot_application = AsyncMock()
    monkeypatch.setattr("app.api.main.build_application", lambda: bot_application)
    stop_scheduler = Mock()
    monkeypatch.setattr("app.api.main.stop_scheduler", stop_scheduler)

    app = FastAPI()
    async with lifespan(app):
        pass

    bot_application.stop.assert_awaited_once()
    bot_application.shutdown.assert_awaited_once()
    stop_scheduler.assert_called_once_with()
