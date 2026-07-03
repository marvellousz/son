import os
from app.tools.base import tool


@tool(
    name="search_knowledge",
    description="Search for keywords or phrases inside all markdown files stored in the knowledge folders.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query or keyword to look for",
            }
        },
        "required": ["query"],
    },
)
def search_knowledge(query: str) -> str:
    knowledge_dir = "knowledge"
    if not os.path.exists(knowledge_dir):
        return (
            "No knowledge files found (the 'knowledge/' directory does not exist yet)."
        )

    query_lower = query.lower().strip()
    results = []

    # Recursively traverse knowledge folder
    for root, _, files in os.walk(knowledge_dir):
        for file in files:
            if not file.endswith(".md"):
                continue

            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            file_match = query_lower in file.lower()
            content_match = query_lower in content.lower()

            if file_match or content_match:
                # Extract a matching snippet
                snippet = ""
                lines = content.splitlines()
                for line in lines:
                    # Skip empty lines or top-level note category headers
                    if not line.strip() or line.startswith("Category:"):
                        continue
                    if query_lower in line.lower():
                        cleaned_line = line.strip("#* ").strip()
                        if cleaned_line:
                            snippet = f'Match: "... {cleaned_line} ..."'
                            break

                # Fallback to first line of content if snippet not found
                if not snippet and lines:
                    for line in lines:
                        cleaned = line.strip("#* ").strip()
                        if cleaned:
                            snippet = f'Preview: "{cleaned[:80]}..."'
                            break

                rel_path = os.path.relpath(filepath, ".")
                results.append(f"📄 **{rel_path}**\n{snippet}")

    if not results:
        return f"No matches found for query: '{query}'."

    return f"🔍 **Knowledge Search Results for '{query}':**\n\n" + "\n\n".join(results)
