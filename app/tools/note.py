import os
import re
from datetime import datetime
from app.database.session import get_db_ctx
from app.database.models import Note
from app.tools.todo import get_or_create_user
from app.tools.base import tool


def slugify(text: str) -> str:
    """Generate a clean slug for filenames."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text.strip("_")[:30]


@tool(
    name="add_note",
    description="Save a new markdown note. Classification (work, personal, docs) is done automatically.",
    parameters={
        "type": "object",
        "properties": {
            "telegram_id": {
                "type": "integer",
                "description": "The Telegram ID of the user",
            },
            "text": {
                "type": "string",
                "description": "The content of the note. Prepend with 'work ' or 'personal ' to force categories, otherwise it defaults to docs.",
            },
        },
        "required": ["telegram_id", "text"],
    },
)
def add_note(telegram_id: int, text: str) -> str:
    # Classify the note category
    text_stripped = text.strip()
    text_lower = text_stripped.lower()

    category = "docs"
    content = text_stripped

    if text_lower.startswith("work "):
        category = "work"
        content = text_stripped[5:].strip()
    elif text_lower.startswith("personal "):
        category = "personal"
        content = text_stripped[9:].strip()
    elif (
        text_lower.startswith("doc ")
        or text_lower.startswith("docs ")
        or text_lower.startswith("today i learned")
    ):
        category = "docs"
        if text_lower.startswith("doc "):
            content = text_stripped[4:].strip()
        elif text_lower.startswith("docs "):
            content = text_stripped[5:].strip()

    # Generate filepath
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = slugify(content)
    if not slug:
        slug = "note"
    filename = f"{timestamp}_{slug}.md"

    # Relative to project workspace root
    relative_path = f"knowledge/{category}/{filename}"
    absolute_path = os.path.abspath(relative_path)

    # Ensure folder exists
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)

    # Markdown template
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    markdown_content = f"""# Note - {now_str}
Category: {category}

{content}
"""

    # Write to file
    with open(absolute_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    # Save to SQLite metadata
    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)
        note = Note(
            user_id=user.id, content=content, filepath=relative_path, category=category
        )
        db.add(note)
        db.commit()

    return f"Saved note to {relative_path} (ID: {note.id})"


@tool(
    name="list_notes",
    description="List all notes. Can optionally filter by category: 'work', 'personal', or 'docs'.",
    parameters={
        "type": "object",
        "properties": {
            "telegram_id": {
                "type": "integer",
                "description": "The Telegram ID of the user",
            },
            "category": {
                "type": "string",
                "enum": ["all", "work", "personal", "docs"],
                "description": "Filter by category: 'work', 'personal', 'docs', or 'all'",
                "default": "all",
            },
        },
        "required": ["telegram_id"],
    },
)
def list_notes(telegram_id: int, category: str = "all") -> str:
    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)
        query = db.query(Note).filter(Note.user_id == user.id)

        if category != "all":
            query = query.filter(Note.category == category)

        notes = query.order_by(Note.created_at.desc()).all()
        if not notes:
            return f"No {category if category != 'all' else ''} notes found."

        lines = []
        for n in notes:
            # Show summary of the first line/content
            snippet = n.content.split("\n")[0][:50]
            if len(n.content) > 50:
                snippet += "..."
            lines.append(
                f"• ID {n.id} [{n.category}]: '{snippet}' (Path: {n.filepath})"
            )
        return "\n".join(lines)
