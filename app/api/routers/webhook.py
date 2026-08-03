"""Telegram webhook endpoint."""

import json
from hmac import compare_digest
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from telegram import Update

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("api.webhook")

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    """Receive a Telegram webhook update and forward it to the bot application."""
    bot_application = getattr(request.app.state, "bot_application", None)
    if bot_application is None:
        raise HTTPException(status_code=503, detail="webhook mode not enabled")

    secret = settings.telegram_webhook_secret
    if secret and not compare_digest(x_telegram_bot_api_secret_token or "", secret):
        logger.warning("webhook_invalid_secret")
        raise HTTPException(status_code=403, detail="invalid secret token")

    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON") from None

    update = Update.de_json(data, bot_application.bot)
    if update is None:
        raise HTTPException(status_code=400, detail="invalid update")

    await bot_application.process_update(update)
    return {"ok": True}
