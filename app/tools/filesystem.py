import os
import logging
import asyncio
from app.tools.base import tool

logger = logging.getLogger(__name__)

def resolve_case_insensitive_path(path: str) -> str:
    """Recursively resolves a path case-insensitively if it does not exist."""
    expanded = os.path.abspath(os.path.expanduser(path.strip()))
    if os.path.exists(expanded):
        return expanded

    # Split the path into directories/file parts
    parts = []
    current = expanded
    while True:
        parent, name = os.path.split(current)
        if not name:
            if current:
                parts.insert(0, current)
            break
        parts.insert(0, name)
        current = parent

    # Reconstruct and match case-insensitively
    resolved = parts[0] if parts else "/"
    for part in parts[1:]:
        if not os.path.exists(resolved) or not os.path.isdir(resolved):
            resolved = os.path.join(resolved, part)
            continue

        try:
            items = os.listdir(resolved)
            match = None
            for item in items:
                if item.lower() == part.lower():
                    match = item
                    break
            if match:
                resolved = os.path.join(resolved, match)
            else:
                resolved = os.path.join(resolved, part)
        except Exception:
            resolved = os.path.join(resolved, part)

    return resolved

@tool(
    name="list_local_directory",
    description="List the contents of a local directory on the user's laptop/filesystem.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative path of the directory to list (e.g., '~/Documents', '.', '/home/user').",
            }
        },
        "required": [],
    },
)
def list_local_directory(path: str = ".", telegram_id: int = None) -> str:
    """Lists files and folders at the specified path, resolving casing automatically."""
    try:
        # Resolve case mismatch if any (e.g., Downloads vs downloads on Linux)
        expanded_path = os.path.abspath(resolve_case_insensitive_path(path))
        
        if not os.path.exists(expanded_path):
            return f"Error: Path '{path}' does not exist."
            
        if not os.path.isdir(expanded_path):
            return f"Error: Path '{path}' is a file, not a directory. Use read_local_file to read it."

        items = os.listdir(expanded_path)
        if not items:
            return f"📁 Directory '{expanded_path}' is empty."

        # Separate files and directories
        dirs = []
        files = []
        for item in sorted(items):
            if item.startswith(".venv") or item == ".git" or item == ".ruff_cache":
                continue
            full_item_path = os.path.join(expanded_path, item)
            if os.path.isdir(full_item_path):
                dirs.append(f"📁 {item}/")
            else:
                try:
                    size_bytes = os.path.getsize(full_item_path)
                    if size_bytes < 1024:
                        size_str = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        size_str = f"{size_bytes / 1024:.1f} KB"
                    else:
                        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                except Exception:
                    size_str = "unknown size"
                files.append(f"📄 {item} ({size_str})")

        output_lines = [f"📂 **Contents of {expanded_path}:**"]
        if dirs:
            output_lines.append("\n**directories:**")
            output_lines.extend(dirs)
        if files:
            output_lines.append("\n**files:**")
            output_lines.extend(files)

        return "\n".join(output_lines)
    except Exception as e:
        logger.error(f"Error listing directory: {e}", exc_info=True)
        return f"Error listing directory '{path}': {str(e)}"

@tool(
    name="read_local_file",
    description="Read the text content of a local file from the user's laptop/filesystem.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative path of the file to read (e.g., '~/Documents/report.txt', 'main.py').",
            },
            "max_lines": {
                "type": "integer",
                "description": "The maximum number of lines to read from the file to avoid hitting context limits (default is 100).",
                "default": 100,
            }
        },
        "required": ["path"],
    },
)
def read_local_file(path: str, max_lines: int = 100, telegram_id: int = None) -> str:
    """Reads the text content of the file up to max_lines, resolving casing automatically."""
    try:
        expanded_path = os.path.abspath(resolve_case_insensitive_path(path))

        if not os.path.exists(expanded_path):
            return f"Error: File '{path}' does not exist."

        if not os.path.isfile(expanded_path):
            return f"Error: Path '{path}' is a directory, not a file. Use list_local_directory to view its contents."

        lines = []
        with open(expanded_path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                lines.append(line)
                if i >= max_lines:
                    lines.append(f"\n... [Truncated after {max_lines} lines] ...")
                    break

        content = "".join(lines)
        return f"📄 **File: {expanded_path}**\n\n```\n{content}\n```"
    except Exception as e:
        logger.error(f"Error reading file: {e}", exc_info=True)
        return f"Error reading file '{path}': {str(e)}"


EXCLUDED_FOLDERS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", 
    ".cache", ".npm", ".cargo", ".rustup", "miniconda3", 
    ".config", ".local", ".vscode", ".idea", ".ruff_cache", 
    ".copilot", ".surprise_data", ".pub-cache", ".supabase"
}

@tool(
    name="fuzzy_find_local_file",
    description="Fuzzy search or find files and folders on your laptop/filesystem matching a name or query.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The file or directory name query to search for (e.g., 'DECISIONS', 'bot.py', 'settings').",
            },
            "path": {
                "type": "string",
                "description": "The directory path to start searching from (defaults to user home directory '~').",
                "default": "~",
            },
            "limit": {
                "type": "integer",
                "description": "Max number of search results to return (default is 10).",
                "default": 10,
            }
        },
        "required": ["query"],
    },
)
def fuzzy_find_local_file(query: str, path: str = "~", limit: int = 10, telegram_id: int = None) -> str:
    """Recursively search for files/directories matching query, skipping cache folders."""
    try:
        query_clean = query.strip().lower()
        if not query_clean:
            return "Error: Search query cannot be empty."

        start_path = os.path.abspath(resolve_case_insensitive_path(path))
        if not os.path.exists(start_path):
            return f"Error: Starting path '{path}' does not exist."

        matches = []
        files_scanned = 0
        max_scanned = 8000 # Prevent infinite walks or performance hogging

        for root, dirs, files in os.walk(start_path, topdown=True):
            # Prune excluded directories in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDED_FOLDERS and not d.startswith(".")]

            # Check directory names
            for d in dirs:
                files_scanned += 1
                if query_clean in d.lower():
                    full_path = os.path.join(root, d)
                    matches.append((full_path, True)) # (path, is_dir)
                    if len(matches) >= limit:
                        break

            if len(matches) >= limit:
                break

            # Check file names
            for f in files:
                files_scanned += 1
                if query_clean in f.lower():
                    full_path = os.path.join(root, f)
                    matches.append((full_path, False))
                    if len(matches) >= limit:
                        break

                if files_scanned >= max_scanned:
                    break

            if len(matches) >= limit or files_scanned >= max_scanned:
                break

        if not matches:
            return f"🔍 **No files matching '{query}' found in '{start_path}'** (scanned {files_scanned} items)."

        lines = [f"🔍 **Found {len(matches)} matches for '{query}' in '{start_path}':**"]
        for idx, (match_path, is_dir) in enumerate(matches, 1):
            icon = "📁" if is_dir else "📄"
            # Format path relative to starting path or show absolute path
            display_path = os.path.relpath(match_path, start_path)
            if display_path == ".":
                display_path = match_path
            else:
                display_path = os.path.join(path, display_path)
            lines.append(f"{idx}. {icon} `{display_path}`")

        if files_scanned >= max_scanned:
            lines.append(f"\n⚠️ *Note: Search stopped early after scanning {files_scanned} items to protect CPU.*")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Fuzzy find error: {e}", exc_info=True)
        return f"Error executing fuzzy search: {str(e)}"


@tool(
    name="send_local_file",
    description="Send a local file (document, image, PDF, etc.) from the user's laptop filesystem directly to the Telegram/Discord chat.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative path of the file to send (e.g., '~/Downloads/son.jpg', 'main.py').",
            }
        },
        "required": ["path"],
    },
)
def send_local_file(path: str, telegram_id: int = None) -> str:
    """Send a local file to the chat platform (Telegram or Discord) matching the user's ID."""
    if not telegram_id:
        return "Error: User ID is required to send a file."

    try:
        expanded_path = os.path.abspath(resolve_case_insensitive_path(path))

        if not os.path.exists(expanded_path):
            return f"Error: File '{path}' does not exist."

        if not os.path.isfile(expanded_path):
            return f"Error: Path '{path}' is a directory. You can only send files."

        # Size check
        size_bytes = os.path.getsize(expanded_path)
        size_mb = size_bytes / (1024 * 1024)
        if size_mb > 50.0:
            return f"Error: File '{path}' is {size_mb:.1f}MB, which exceeds the upload limit (max 50MB)."

        # Try to send via Discord if the bot is active and user is on Discord
        from app.discord_bot.bot import discord_bot
        from app.config.settings import settings
        import discord

        sent_on_discord = False
        if discord_bot and discord_bot.is_ready():
            try:
                async def send_discord_file():
                    user = await discord_bot.fetch_user(telegram_id)
                    if user:
                        with open(expanded_path, "rb") as f:
                            discord_file = discord.File(f, filename=os.path.basename(expanded_path))
                            await user.send(
                                content=f"📄 Here is your file: **{os.path.basename(expanded_path)}**",
                                file=discord_file
                            )
                        return True
                    return False

                future = asyncio.run_coroutine_threadsafe(send_discord_file(), discord_bot.loop)
                sent_on_discord = future.result(timeout=30.0)
            except Exception as de:
                logger.debug(f"Did not send via Discord: {de}")

        if sent_on_discord:
            return f"📤 File '{os.path.basename(expanded_path)}' sent successfully via Discord!"

        # Fallback to Telegram
        from telegram import Bot
        
        if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
            return "Error: Telegram bot is not configured."

        async def send_telegram_file():
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            async with bot:
                with open(expanded_path, "rb") as f:
                    await bot.send_document(
                        chat_id=telegram_id,
                        document=f,
                        filename=os.path.basename(expanded_path),
                        caption=f"📄 Here is your file: {os.path.basename(expanded_path)}"
                    )

        asyncio.run(send_telegram_file())
        return f"📤 File '{os.path.basename(expanded_path)}' sent successfully via Telegram!"

    except Exception as e:
        logger.error(f"Error sending local file: {e}", exc_info=True)
        return f"Error sending local file '{path}': {str(e)}"


