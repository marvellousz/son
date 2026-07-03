from datetime import datetime
from app.database.session import get_db_ctx
from app.database.models import User, Todo
from app.tools.base import tool


def get_or_create_user(db, telegram_id: int) -> User:
    """Helper to retrieve or create a user by Telegram ID."""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@tool(
    name="add_todo",
    description="Add a new todo item to the user's checklist.",
    parameters={
        "type": "object",
        "properties": {
            "telegram_id": {
                "type": "integer",
                "description": "The Telegram ID of the user",
            },
            "title": {"type": "string", "description": "The text of the todo to add"},
        },
        "required": ["telegram_id", "title"],
    },
)
def add_todo(telegram_id: int, title: str) -> str:
    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)
        todo = Todo(user_id=user.id, title=title)
        db.add(todo)
        db.commit()
        return f"Added todo: '{title}' (ID: {todo.id})"


@tool(
    name="list_todos",
    description="List the user's todo items. Can filter by status: 'pending', 'completed', or 'all'.",
    parameters={
        "type": "object",
        "properties": {
            "telegram_id": {
                "type": "integer",
                "description": "The Telegram ID of the user",
            },
            "status": {
                "type": "string",
                "enum": ["all", "pending", "completed"],
                "description": "Filter by status: 'pending', 'completed', or 'all'",
                "default": "all",
            },
        },
        "required": ["telegram_id"],
    },
)
def list_todos(telegram_id: int, status: str = "all") -> str:
    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)
        query = db.query(Todo).filter(Todo.user_id == user.id)

        if status == "pending":
            query = query.filter(Todo.is_completed.is_(False))
        elif status == "completed":
            query = query.filter(Todo.is_completed.is_(True))

        todos = query.order_by(Todo.created_at.asc()).all()
        if not todos:
            return f"No {status if status != 'all' else ''} todos found."

        lines = []
        for t in todos:
            chk = "✓" if t.is_completed else " "
            lines.append(f"[{chk}] {t.id}: {t.title}")
        return "\n".join(lines)


@tool(
    name="complete_todo",
    description="Mark a specific todo item as completed by its ID.",
    parameters={
        "type": "object",
        "properties": {
            "telegram_id": {
                "type": "integer",
                "description": "The Telegram ID of the user",
            },
            "todo_id": {
                "type": "integer",
                "description": "The ID of the todo to mark complete",
            },
        },
        "required": ["telegram_id", "todo_id"],
    },
)
def complete_todo(telegram_id: int, todo_id: int) -> str:
    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)
        todo = (
            db.query(Todo).filter(Todo.id == todo_id, Todo.user_id == user.id).first()
        )
        if not todo:
            return f"Todo with ID {todo_id} not found."

        todo.is_completed = True
        todo.completed_at = datetime.utcnow()
        db.commit()
        return f"Marked todo '{todo.title}' (ID: {todo_id}) as completed."
