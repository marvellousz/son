from html.parser import HTMLParser
import httpx
import logging
import re
from app.tools.base import tool

logger = logging.getLogger(__name__)


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.ignore = False

    def handle_starttag(self, tag, attrs):
        if tag in [
            "script",
            "style",
            "head",
            "meta",
            "link",
            "nav",
            "footer",
            "header",
        ]:
            self.ignore = True

    def handle_endtag(self, tag):
        if tag in [
            "script",
            "style",
            "head",
            "meta",
            "link",
            "nav",
            "footer",
            "header",
        ]:
            self.ignore = False

    def handle_data(self, data):
        if not self.ignore:
            cleaned = data.strip()
            if cleaned:
                self.text.append(cleaned)


@tool(
    name="fetch_webpage",
    description="Fetch and read the text content of a specific webpage URL to extract detailed information.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The absolute URL of the webpage to fetch (e.g. from search_web results)",
            }
        },
        "required": ["url"],
    },
)
def fetch_webpage(url: str, telegram_id: int = None) -> str:
    """Fetch a webpage URL and extract its text content."""
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        return "Error: Invalid URL. URL must start with http:// or https://"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    logger.info(f"Fetching webpage content for: {url}")
    try:
        response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        if response.status_code != 200:
            return f"Error: Unable to fetch webpage (HTTP {response.status_code})."

        parser = TextExtractor()
        parser.feed(response.text)

        full_text = "\n".join(parser.text)

        # Clean up whitespace and empty lines
        full_text = re.sub(r"\n+", "\n", full_text)
        full_text = re.sub(r"[ \t]+", " ", full_text)

        # Limit the output size to avoid blowing up the LLM context window
        max_chars = 3000
        if len(full_text) > max_chars:
            return (
                full_text[:max_chars] + "\n\n... [Content truncated due to length] ..."
            )

        return full_text if full_text.strip() else "Webpage contains no readable text."
    except Exception as e:
        logger.error(f"Webpage fetch error: {e}", exc_info=True)
        return f"Error fetching webpage: {str(e)}"
