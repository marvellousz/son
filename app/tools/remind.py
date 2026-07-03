from datetime import datetime
import dateparser
from app.database.session import get_db_ctx
from app.database.models import Reminder
from app.tools.todo import get_or_create_user
from app.tools.base import tool


def parse_time_expression(expr: str) -> datetime | None:
    """Parses natural language date/time expressions into datetime objects."""
    now = datetime.now()
    # dateparser settings to prefer future dates for ambiguous terms
    dt = dateparser.parse(
        expr,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": now,
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )
    return dt


@tool(
    name="add_reminder",
    description="Schedule a reminder notification for a specific time or duration.",
    parameters={
        "type": "object",
        "properties": {
            "telegram_id": {
                "type": "integer",
                "description": "The Telegram ID of the user",
            },
            "text": {"type": "string", "description": "The message to be reminded of"},
            "time_expr": {
                "type": "string",
                "description": "Time expression, e.g., 'tomorrow 8pm', 'in 2 hours', 'next monday noon'",
            },
        },
        "required": ["telegram_id", "text", "time_expr"],
    },
)
def add_reminder(telegram_id: int, text: str, time_expr: str) -> str:
    due_at = parse_time_expression(time_expr)
    if not due_at:
        return f"Could not parse time expression: '{time_expr}'. Please try a clearer format."

    # Check if due_at is in the past
    now = datetime.now()
    if due_at < now:
        return f"The computed time ({due_at.strftime('%Y-%m-%d %H:%M:%S')}) is in the past. Reminders must be in the future."

    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)
        reminder = Reminder(user_id=user.id, text=text, due_at=due_at)
        db.add(reminder)
        db.commit()
        return f"Reminder set: '{text}' for {due_at.strftime('%Y-%m-%d %H:%M:%S')} (ID: {reminder.id})."


@tool(
    name="list_reminders",
    description="List the user's pending scheduled reminders.",
    parameters={
        "type": "object",
        "properties": {
            "telegram_id": {
                "type": "integer",
                "description": "The Telegram ID of the user",
            }
        },
        "required": ["telegram_id"],
    },
)
def list_reminders(telegram_id: int) -> str:
    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)
        reminders = (
            db.query(Reminder)
            .filter(Reminder.user_id == user.id, Reminder.is_sent.is_(False))
            .order_by(Reminder.due_at.asc())
            .all()
        )
        if not reminders:
            return "No pending reminders."

        lines = []
        for r in reminders:
            lines.append(
                f"• ID {r.id}: '{r.text}' due at {r.due_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        return "\n".join(lines)
