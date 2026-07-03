import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.error import TelegramError
from app.config.settings import settings
from app.database.session import get_db_ctx
from app.database.models import Reminder, User

logger = logging.getLogger(__name__)


async def check_reminders() -> None:
    """Poll database for reminders that are due and send them via Telegram."""
    if (
        settings.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here"
        or not settings.TELEGRAM_BOT_TOKEN
    ):
        logger.debug("Telegram bot token not configured. Skipping scheduler run.")
        return

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    now = datetime.utcnow()

    with get_db_ctx() as db:
        # Get pending reminders that are past due
        due_reminders = (
            db.query(Reminder)
            .filter(Reminder.due_at <= now, Reminder.is_sent.is_(False))
            .all()
        )

        if not due_reminders:
            return

        logger.info(f"Processing {len(due_reminders)} due reminders...")

        for reminder in due_reminders:
            user = db.query(User).filter(User.id == reminder.user_id).first()
            if not user:
                logger.error(f"User not found for reminder {reminder.id}")
                continue

            try:
                # Format reminder message
                msg_text = f"🔔 **Reminder:** {reminder.text}"

                # 1. Try sending via Discord first if bot is running and user exists
                sent_via_discord = False
                from app.discord_bot.bot import get_discord_bot_instance
                discord_bot = get_discord_bot_instance()
                if discord_bot and discord_bot.is_ready():
                    try:
                        discord_user = await discord_bot.fetch_user(user.telegram_id)
                        if discord_user:
                            await discord_user.send(msg_text)
                            sent_via_discord = True
                            logger.info(
                                f"Successfully sent reminder {reminder.id} to Discord user {user.telegram_id}"
                            )
                    except Exception as de:
                        logger.debug(
                            f"Could not send to Discord user {user.telegram_id}: {de}"
                        )

                # 2. Fallback to Telegram if not sent via Discord
                if not sent_via_discord:
                    await bot.send_message(
                        chat_id=user.telegram_id, text=msg_text, parse_mode="Markdown"
                    )
                    logger.info(
                        f"Successfully sent reminder {reminder.id} to Telegram user {user.telegram_id}"
                    )

                # Mark as sent
                reminder.is_sent = True
            except TelegramError as te:
                logger.error(
                    f"Telegram error sending reminder {reminder.id} to user {user.telegram_id}: {te}"
                )
                # Avoid retrying forever for invalid chat
                if "Forbidden" in str(te) or "chat not found" in str(te):
                    reminder.is_sent = True
            except Exception as e:
                logger.error(
                    f"General exception sending reminder {reminder.id}: {e}",
                    exc_info=True,
                )

        db.commit()


# Create scheduler instance
scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    """Start background jobs scheduler."""
    scheduler.add_job(
        check_reminders,
        "interval",
        minutes=1,
        id="reminder_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Apscheduler background jobs started (interval=1 minute).")
