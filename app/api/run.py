"""API entry point. Run separately from the bot polling process."""

import uvicorn

from app.api.main import create_app
from app.core.config import settings
from app.core.logger import setup_logging


def run() -> None:
    setup_logging(settings.log_level)
    uvicorn.run(
        create_app(),
        host=settings.api_host,
        port=settings.api_port,
    )


if __name__ == "__main__":
    run()
