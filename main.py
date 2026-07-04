import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from app.config.settings import settings
from app.api.routes import router as api_router
from app.scheduler.tasks import start_scheduler, scheduler
from app.telegram.bot import start_bot, stop_bot
from app.discord_bot.bot import start_discord_bot, stop_discord_bot
from app.tools.clipboard import start_clipboard_monitor
from alembic.config import Config
from alembic import command

# Basic logging configuration
logging.basicConfig(
    level=logging.getLevelName(settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("son-assistant")


def run_db_migrations() -> None:
    """Run database migrations programmatically on application startup."""
    logger.info("Initiating programmatic database migrations via Alembic...")
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic database migrations applied successfully.")
    except Exception as e:
        logger.error(f"Alembic database migration execution failed: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Apply database schemas and migrations
    run_db_migrations()

    # 2. Start Background task scheduler
    start_scheduler()

    # 3. Start Laptop Clipboard Synchronization Monitor
    start_clipboard_monitor()

    # 3. Start Telegram Bot Polling loop in background task
    bot_task = asyncio.create_task(start_bot())

    def handle_bot_exit(task):
        try:
            task.result()
        except Exception as e:
            logger.error(f"Telegram bot background task failed: {e}", exc_info=True)

    bot_task.add_done_callback(handle_bot_exit)

    # 4. Start Discord Bot Gateway loop in background task if configured
    discord_task = None
    if settings.DISCORD_BOT_TOKEN and settings.DISCORD_BOT_TOKEN != "your_discord_bot_token_here":
        discord_task = asyncio.create_task(start_discord_bot())

        def handle_discord_exit(task):
            try:
                task.result()
            except Exception as e:
                logger.error(f"Discord bot background task failed: {e}", exc_info=True)

        discord_task.add_done_callback(handle_discord_exit)

    yield

    # 5. Graceful Shutdown triggers
    logger.info("Beginning graceful shutdown sequence...")
    # Stop telegram polling
    await stop_bot()
    # Cancel bot task
    bot_task.cancel()
    # Stop Discord bot client connection
    if discord_task:
        await stop_discord_bot()
        discord_task.cancel()
    # Stop scheduler
    scheduler.shutdown()
    logger.info("Son Personal Assistant shutdown complete.")


app = FastAPI(
    title="Son Personal Assistant Core",
    description="FastAPI service serving as the HTTP hook/API and hosting the Son Telegram orchestrator.",
    version="0.1.0",
    lifespan=lifespan,
)

# Bind FastAPI endpoints
app.include_router(api_router)

if __name__ == "__main__":
    logger.info("Launching Son Uvicorn process...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")
