import subprocess
import threading
import time
import logging
from datetime import datetime
from app.tools.base import tool
from app.database.session import get_db_ctx
from app.database.models import ClipboardHistory

logger = logging.getLogger(__name__)

# Cache for the last clipboard value to avoid redundant database lookups/writes
_last_clipboard_value = None

def get_current_laptop_clipboard() -> str | None:
    """Get the current clipboard content using wl-paste."""
    try:
        result = subprocess.run(
            ["wl-paste", "-n"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=True
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.debug("wl-paste timed out")
        return None
    except Exception as e:
        logger.debug(f"Could not read Wayland clipboard: {e}")
        return None

def set_laptop_clipboard(text: str) -> bool:
    """Set the laptop clipboard content using wl-copy."""
    try:
        subprocess.run(
            ["wl-copy"],
            input=text,
            text=True,
            timeout=2.0,
            check=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to set Wayland clipboard: {e}", exc_info=True)
        return False

def clipboard_monitor_loop():
    """Background loop polling wl-paste for changes."""
    global _last_clipboard_value
    logger.info("Wayland clipboard monitor thread started.")
    
    # Initialize the last value from the database or the current clipboard on start
    with get_db_ctx() as db:
        last_db_entry = db.query(ClipboardHistory).order_by(ClipboardHistory.id.desc()).first()
        if last_db_entry:
            _last_clipboard_value = last_db_entry.content
            
    if _last_clipboard_value is None:
        _last_clipboard_value = get_current_laptop_clipboard()

    while True:
        try:
            current_value = get_current_laptop_clipboard()
            if current_value and current_value != _last_clipboard_value:
                logger.info(f"New clipboard value detected, saving to history: {current_value[:50]}...")
                
                with get_db_ctx() as db:
                    new_entry = ClipboardHistory(content=current_value)
                    db.add(new_entry)
                    db.commit()
                    
                _last_clipboard_value = current_value
        except Exception as e:
            logger.error(f"Error in clipboard monitor thread: {e}", exc_info=True)
            
        time.sleep(1.5)

def start_clipboard_monitor() -> None:
    """Start the clipboard monitor as a background daemon thread."""
    # Check if wl-paste is available
    try:
        subprocess.run(["which", "wl-paste"], check=True, capture_output=True)
    except Exception:
        logger.warning("wl-paste utility not found. Clipboard history monitoring is disabled.")
        return

    thread = threading.Thread(target=clipboard_monitor_loop, daemon=True, name="ClipboardMonitor")
    thread.start()

@tool(
    name="get_clipboard_history",
    description="Retrieve the last few items copied to the laptop clipboard history.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of history items to retrieve (default is 5).",
                "default": 5,
            }
        },
        "required": [],
    },
)
def get_clipboard_history(limit: int = 5, telegram_id: int = None) -> str:
    """Retrieve clipboard logs from SQLite database."""
    with get_db_ctx() as db:
        history = (
            db.query(ClipboardHistory)
            .order_by(ClipboardHistory.created_at.desc())
            .limit(limit)
            .all()
        )
        
        current = get_current_laptop_clipboard()

        if not history and not current:
            return "📋 Clipboard history is currently empty, son!"

        lines = ["📋 **Laptop Clipboard Sync:**"]
        if current:
            lines.append(f"\n**current active clipboard:**\n`{current}`\n")
            
        if history:
            lines.append("**recent history:**")
            for idx, item in enumerate(history, 1):
                # Clean presentation of newlines
                snippet = item.content.replace("\n", " ↵ ")
                if len(snippet) > 60:
                    snippet = snippet[:60] + "..."
                timestamp = item.created_at.strftime("%H:%M:%S")
                lines.append(f"{idx}. [{timestamp}] {snippet}")
                
        return "\n".join(lines)

@tool(
    name="write_to_clipboard",
    description="Copy text directly to the laptop's clipboard (remote copy).",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text content to copy to the laptop's clipboard.",
            }
        },
        "required": ["text"],
    },
)
def write_to_clipboard(text: str, telegram_id: int = None) -> str:
    """Set the clipboard on the laptop using wl-copy."""
    global _last_clipboard_value
    text_stripped = text.strip()
    if not text_stripped:
        return "Error: Cannot copy empty text."

    success = set_laptop_clipboard(text_stripped)
    if success:
        _last_clipboard_value = text_stripped
        # Log to db history too
        try:
            with get_db_ctx() as db:
                new_entry = ClipboardHistory(content=text_stripped)
                db.add(new_entry)
                db.commit()
        except Exception as e:
            logger.error(f"Failed to log remote copy to DB: {e}")
            
        return f"📋 **Copied successfully to laptop, son!**\n`{text_stripped}`"
    else:
        return "❌ **Failed to copy to laptop. Is Wayland active?**"
