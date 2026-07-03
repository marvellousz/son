import xml.etree.ElementTree as ET
import httpx
import logging
import re
from app.tools.base import tool

logger = logging.getLogger(__name__)


def fetch_rss_news(feed_url: str, limit: int = 5) -> list:
    """Fetch and parse items from a public RSS feed."""
    try:
        response = httpx.get(feed_url, timeout=10.0, follow_redirects=True)
        if response.status_code != 200:
            logger.warning(
                f"Failed to fetch RSS feed {feed_url}: HTTP {response.status_code}"
            )
            return []

        # Parse XML
        root = ET.fromstring(response.content)
        items = []
        for item in root.findall(".//item")[:limit]:
            title_el = item.find("title")
            desc_el = item.find("description")
            link_el = item.find("link")

            title = title_el.text if title_el is not None else "No Title"
            desc = desc_el.text if desc_el is not None else ""
            link = link_el.text if link_el is not None else ""

            # Clean HTML tags from description
            desc = re.sub(r"<[^>]*>", "", desc).strip()
            # Clean up white spaces
            desc = re.sub(r"\s+", " ", desc)

            if len(desc) > 180:
                desc = desc[:180] + "..."

            items.append({"title": title, "description": desc, "link": link})
        return items
    except Exception as e:
        logger.error(f"Error fetching RSS: {e}", exc_info=True)
        return []


@tool(
    name="get_news",
    description="Fetch and summarize the latest news for any category, topic, or search query.",
    parameters={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "The category, topic, or search query of news to fetch (e.g. 'sports', 'business', 'artificial intelligence', 'science', 'politics')",
                "default": "world",
            }
        },
        "required": ["category"],
    },
)
def get_news(category: str = "world") -> str:
    category = category.lower().strip()

    import urllib.parse

    encoded_category = urllib.parse.quote(category)
    url = f"https://news.google.com/rss/search?q={encoded_category}&hl=en-US&gl=US&ceid=US:en"

    logger.info(f"Fetching news for category '{category}' from {url}")
    items = fetch_rss_news(url, limit=5)

    if not items:
        # Fallback mocks if offline
        logger.warning("No news fetched. Using mock fallbacks.")
        items = [
            {
                "title": f"Breaking news update in {category.capitalize()}",
                "description": f"No active connection to live news feeds. Check back later for up-to-date reports on {category}.",
                "link": "https://news.google.com",
            }
        ]

    header = f"📰 **Latest {category.upper()} News**\n\n"
    blocks = []
    for idx, item in enumerate(items, 1):
        block = f"{idx}. **{item['title']}**\n{item['description']}\n[Read more]({item['link']})"
        blocks.append(block)

    return header + "\n\n".join(blocks)
