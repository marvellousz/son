from html.parser import HTMLParser
import urllib.parse
import httpx
import logging
from app.tools.base import tool

logger = logging.getLogger(__name__)


class DDGHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.current_result = None
        self.in_title = False
        self.in_snippet = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")

        if tag == "a" and "result__a" in cls:
            self.current_result = {
                "title": "",
                "link": attrs_dict.get("href", ""),
                "snippet": "",
            }
            self.in_title = True
        elif tag == "a" and "result__snippet" in cls:
            if not self.current_result:
                self.current_result = {
                    "title": "",
                    "link": attrs_dict.get("href", ""),
                    "snippet": "",
                }
            self.in_snippet = True

    def handle_endtag(self, tag):
        if tag == "a":
            if self.in_title:
                self.in_title = False
            elif self.in_snippet:
                self.in_snippet = False
                if self.current_result:
                    self.current_result["title"] = self.current_result["title"].strip()
                    self.current_result["snippet"] = self.current_result[
                        "snippet"
                    ].strip()
                    self.results.append(self.current_result)
                    self.current_result = None

    def handle_data(self, data):
        if self.current_result:
            if self.in_title:
                self.current_result["title"] += data
            elif self.in_snippet:
                self.current_result["snippet"] += data


@tool(
    name="search_web",
    description="Search the web (Google/DuckDuckGo) for real-time information, answers to general questions, or recent events.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to lookup on the web",
            }
        },
        "required": ["query"],
    },
)
def search_web(query: str, telegram_id: int = None) -> str:
    """Perform a web search for a query and return formatted snippets."""
    query = query.strip()
    encoded_query = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    logger.info(f"Performing web search for: '{query}'")
    try:
        response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        if response.status_code != 200:
            return f"Error: Unable to search the web (HTTP {response.status_code})."

        parser = DDGHTMLParser()
        parser.feed(response.text)

        if not parser.results:
            return "No web search results found for this query."

        header = f"🌐 **Web Search Results for '{query}'**\n\n"
        blocks = []
        for idx, res in enumerate(parser.results[:5], 1):
            title = res["title"] or "Link"
            snippet = res["snippet"] or "No description available."
            link = res["link"] or "#"
            blocks.append(f"{idx}. **{title}**\n{snippet}\n[Read more]({link})")

        return header + "\n\n".join(blocks)
    except Exception as e:
        logger.error(f"Web search error: {e}", exc_info=True)
        return f"Error executing web search: {str(e)}"
