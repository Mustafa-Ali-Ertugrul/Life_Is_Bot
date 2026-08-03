"""FastAPI application factory for the Life Is Bot API."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi.errors import RateLimitExceeded

from app.api import API_VERSION
from app.api.exceptions import register_exception_handlers
from app.api.rate_limit import limiter
from app.api.routers.habits import router as habits_router
from app.api.routers.health import router as health_router
from app.api.routers.medications import router as medications_router
from app.api.routers.reports import router as reports_router
from app.api.routers.sport import router as sport_router
from app.api.routers.step import router as step_router
from app.api.routers.supplement import router as supplement_router
from app.api.routers.webhook import router as webhook_router
from app.core.config import settings
from app.core.logger import get_logger
from app.scheduler.engine import stop_scheduler
from app.tgbot.adapter import (
    ApplicationT,
    build_application,
    start_application,
    stop_application,
)

logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("api starting", version=API_VERSION)
    bot_application: ApplicationT | None = None
    if settings.webhook_mode:
        bot_application = build_application()
        await start_application(
            bot_application,
            webhook_url=settings.telegram_webhook_url,
            webhook_secret=settings.telegram_webhook_secret,
        )
        app.state.bot_application = bot_application
        logger.info("api webhook mode enabled")
    yield
    if bot_application is not None:
        await stop_application(bot_application)
        stop_scheduler()
    logger.info("api stopped")


def _retry_after_seconds(request: Request) -> int:
    """Seconds until the rate-limit window resets, with a safe fallback."""
    view_rate_limit = getattr(request.state, "view_rate_limit", None)
    if view_rate_limit is None:
        return 60
    limit_item, keys = view_rate_limit
    reset_time, _remaining = limiter.limiter.get_window_stats(limit_item, *keys)
    return max(int(1 + reset_time - time.time()), 1)


def create_app() -> FastAPI:
    app = FastAPI(title="Life Is Bot API", version=API_VERSION, lifespan=lifespan)

    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
        view_rate_limit = getattr(request.state, "view_rate_limit", None)
        retry_after = _retry_after_seconds(request)
        response = JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "retry_after": retry_after},
        )
        return limiter._inject_headers(response, view_rate_limit)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(habits_router)
    app.include_router(medications_router)
    app.include_router(reports_router)
    app.include_router(sport_router)
    app.include_router(step_router)
    app.include_router(supplement_router)
    app.include_router(webhook_router)
    return app


app = create_app()
