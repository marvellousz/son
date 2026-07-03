from app.database.session import get_db_ctx
from app.database.models import Preference
from app.tools.todo import get_or_create_user
from app.tools.base import tool


@tool(
    name="save_preference",
    description="Save or update a user preference (e.g. key='theme', value='dark').",
    parameters={
        "type": "object",
        "properties": {
            "telegram_id": {
                "type": "integer",
                "description": "The Telegram ID of the user",
            },
            "key": {
                "type": "string",
                "description": "The preference key (e.g., 'theme', 'preferred_name', 'habit')",
            },
            "value": {
                "type": "string",
                "description": "The value of the preference to store",
            },
        },
        "required": ["telegram_id", "key", "value"],
    },
)
def save_preference(telegram_id: int, key: str, value: str) -> str:
    key_clean = key.lower().strip()
    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)

        pref = (
            db.query(Preference)
            .filter(Preference.user_id == user.id, Preference.key == key_clean)
            .first()
        )
        if pref:
            pref.value = value
        else:
            pref = Preference(user_id=user.id, key=key_clean, value=value)
            db.add(pref)

        db.commit()
        return f"Saved user preference: {key_clean} = '{value}'"


@tool(
    name="get_preferences",
    description="Retrieve all saved preferences and facts for a user.",
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
def get_preferences(telegram_id: int) -> str:
    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)
        prefs = db.query(Preference).filter(Preference.user_id == user.id).all()
        if not prefs:
            return "No preferences or facts saved yet."

        lines = ["⚙️ **Saved Preferences & Facts:**"]
        for p in prefs:
            lines.append(f"  • {p.key}: {p.value}")
        return "\n".join(lines)
