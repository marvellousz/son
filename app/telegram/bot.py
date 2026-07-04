import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from app.config.settings import settings
from app.telegram.handlers import (
    start_handler,
    help_handler,
    todo_handler,
    news_handler,
    remind_handler,
    note_handler,
    search_handler,
    daily_handler,
    chat_message_handler,
    google_handler,
    profile_handler,
    eat_handler,
    macros_handler,
    clip_handler,
    find_handler,
    send_file_handler,
)

logger = logging.getLogger(__name__)

# Global Application container
bot_app = None


def init_bot() -> Application | None:
    """Initializes the Telegram bot application, registering all commands."""
    global bot_app
    if (
        settings.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here"
        or not settings.TELEGRAM_BOT_TOKEN
    ):
        logger.warning(
            "TELEGRAM_BOT_TOKEN is not set or using placeholder. Bot will not start."
        )
        return None

    logger.info("Initializing python-telegram-bot application...")
    bot_app = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # Command handlers
    bot_app.add_handler(CommandHandler("start", start_handler))
    bot_app.add_handler(CommandHandler("help", help_handler))
    bot_app.add_handler(CommandHandler("todo", todo_handler))
    bot_app.add_handler(CommandHandler("news", news_handler))
    bot_app.add_handler(CommandHandler("remind", remind_handler))
    bot_app.add_handler(CommandHandler("note", note_handler))
    bot_app.add_handler(CommandHandler("search", search_handler))
    bot_app.add_handler(CommandHandler("google", google_handler))
    bot_app.add_handler(CommandHandler("profile", profile_handler))
    bot_app.add_handler(CommandHandler("eat", eat_handler))
    bot_app.add_handler(CommandHandler("macros", macros_handler))
    bot_app.add_handler(CommandHandler("daily", daily_handler))
    bot_app.add_handler(CommandHandler("clip", clip_handler))
    bot_app.add_handler(CommandHandler("find", find_handler))
    bot_app.add_handler(CommandHandler("send", send_file_handler))

    # Natural language chat message handler
    bot_app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message_handler)
    )

    return bot_app


async def start_bot() -> None:
    """Starts the Telegram bot polling mechanism asynchronously."""
    global bot_app
    if bot_app is None:
        init_bot()

    if bot_app:
        logger.info("Starting Telegram Bot Updater polling loop...")
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        logger.info("Telegram Bot is actively polling.")


async def stop_bot() -> None:
    """Gracefully shuts down the Telegram bot polling and execution resources."""
    global bot_app
    if bot_app:
        logger.info("Stopping Telegram Bot polling loop...")
        if bot_app.updater.running:
            await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()
        logger.info("Telegram Bot has shutdown successfully.")
