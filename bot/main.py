import asyncio
import logging

from telegram.ext import Application

from .config import get_settings
from .db.database import init_db
from .handlers.start import get_start_handler
from .handlers.download import get_download_handler
from .handlers.help import get_help_handler
from .handlers.stats import get_stats_handler
from .handlers.contact import get_contact_handler
from .handlers.health import get_health_handler
from .services.instagram_downloader import close_http_client


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )

    init_db()

    settings = get_settings()

    application = (
        Application.builder()
        .token(settings.bot_token)
        .build()
    )

    application.add_handler(get_start_handler())
    application.add_handler(get_help_handler())
    application.add_handler(get_contact_handler())
    application.add_handler(get_stats_handler())
    application.add_handler(get_health_handler())
    application.add_handler(get_download_handler())

    await application.initialize()
    await application.start()

    try:
        await application.updater.start_polling()
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        # HTTP client ni yopish
        await close_http_client()


if __name__ == "__main__":
    asyncio.run(main())
