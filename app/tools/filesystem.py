import os
import logging
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
