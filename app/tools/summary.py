from datetime import datetime, timedelta
from app.database.session import get_db_ctx
from app.database.models import Todo, Reminder, Note
from app.tools.todo import get_or_create_user
from app.tools.base import tool


@tool(
    name="generate_daily_summary",
    description="Generate a formatted daily summary containing todos completed, reminders scheduled, and notes saved in the last 24 hours.",
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
def generate_daily_summary(telegram_id: int) -> str:
    cutoff_past = datetime.utcnow() - timedelta(hours=24)
    cutoff_future = datetime.utcnow() + timedelta(hours=24)

    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)

        # 1. Completed todos in the last 24 hours
        completed_todos = (
            db.query(Todo)
            .filter(
                Todo.user_id == user.id,
                Todo.is_completed.is_(True),
                Todo.completed_at >= cutoff_past,
            )
            .all()
        )

        # 2. Reminders due in the past 24 hours or next 24 hours
        reminders = (
            db.query(Reminder)
            .filter(
                Reminder.user_id == user.id,
                Reminder.due_at >= cutoff_past,
                Reminder.due_at <= cutoff_future,
            )
            .order_by(Reminder.due_at.asc())
            .all()
        )

        # 3. Notes created in the last 24 hours
        notes = (
            db.query(Note)
            .filter(Note.user_id == user.id, Note.created_at >= cutoff_past)
            .all()
        )

        # Generate summary content
        lines = [f"🌅 **Daily Summary for User (Telegram ID: {telegram_id})**\n"]

        # Todos section
        lines.append("✅ **Completed Todos (Last 24h):**")
        if completed_todos:
            for t in completed_todos:
                lines.append(f"  • {t.title}")
        else:
            lines.append("  _No todos completed in the last 24 hours._")

        lines.append("")

        # Reminders section
        lines.append("🔔 **Reminders (Today & Tomorrow):**")
        if reminders:
            for r in reminders:
                status = "🟢 Done" if r.is_sent else "⏳ Pending"
                lines.append(f"  • [{status}] {r.due_at.strftime('%H:%M')}: {r.text}")
        else:
            lines.append("  _No reminders scheduled in this window._")

        lines.append("")

        # Notes section
        lines.append("📝 **Notes Logged (Last 24h):**")
        if notes:
            for n in notes:
                snippet = n.content.split("\n")[0][:50]
                lines.append(
                    f"  • [{n.category.upper()}] {snippet} (Path: {n.filepath})"
                )
        else:
            lines.append("  _No notes created in the last 24 hours._")

        return "\n".join(lines)
