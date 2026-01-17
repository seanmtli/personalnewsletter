import json
from datetime import datetime
from anthropic import Anthropic
from app.services.content.base import ContentProvider
from app.schemas import ContentItem
from app.config import get_settings

settings = get_settings()

CURATOR_PROMPT = """You are a sports news curator. The user follows these teams/players:
{interests}

Search the web for the most important and interesting sports news from the past week
related to these interests. Find content from:
- News articles (ESPN, The Athletic, team sites, local news)
- Notable tweets from players, reporters, or team accounts
- YouTube highlights or interviews
- Interesting Reddit discussions

Select the TOP 5-7 stories. For each, provide:
- headline: A compelling headline
- summary: 2-3 sentence summary
- source_type: "article" | "tweet" | "video" | "reddit"
- source_name: The publication or account name
- url: Direct link to the content
- relevance: One sentence on why this matters to this fan
- published_at: ISO datetime if known, null if unknown
- thumbnail_url: Image URL if available, null otherwise

Return ONLY valid JSON as an array of objects matching this schema. No other text.
Prioritize: game results, trades, injuries, viral moments, analysis.
Skip: paywalled content, broken links, low-quality sources.

Example format:
[
  {{
    "headline": "Warriors Win Game 7 in OT Thriller",
    "summary": "Stephen Curry scored 42 points...",
    "source_type": "article",
    "source_name": "ESPN",
    "url": "https://espn.com/...",
    "relevance": "Major playoff victory for your team",
    "published_at": "2024-01-15T20:00:00Z",
    "thumbnail_url": null
  }}
]"""


class ClaudeProvider(ContentProvider):
    """Content provider using Claude API with web search."""

    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)

    @property
    def name(self) -> str:
        return "claude"

    async def fetch_content(self, interests: list[str]) -> list[ContentItem]:
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key not configured")

        interests_str = ", ".join(interests)
        prompt = CURATOR_PROMPT.format(interests=interests_str)

        try:
            # Use Claude with web search tool
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 10,
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            # Extract text content from response
            result_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    result_text = block.text
                    break

            # Parse JSON response
            items = self._parse_response(result_text)
            return items

        except Exception as e:
            print(f"Claude API error: {e}")
            raise

    def _parse_response(self, response_text: str) -> list[ContentItem]:
        """Parse Claude's JSON response into ContentItem objects."""
        try:
            # Try to extract JSON from the response
            text = response_text.strip()

            # Handle case where response might have markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)

            items = []
            for item_data in data:
                # Parse published_at if present
                published_at = None
                if item_data.get("published_at"):
                    try:
                        published_at = datetime.fromisoformat(
                            item_data["published_at"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                item = ContentItem(
                    headline=item_data.get("headline", ""),
                    summary=item_data.get("summary", ""),
                    source_type=item_data.get("source_type", "article"),
                    source_name=item_data.get("source_name", "Unknown"),
                    url=item_data.get("url", ""),
                    relevance=item_data.get("relevance", ""),
                    published_at=published_at,
                    thumbnail_url=item_data.get("thumbnail_url"),
                )
                items.append(item)

            return items

        except json.JSONDecodeError as e:
            print(f"Failed to parse Claude response: {e}")
            print(f"Response text: {response_text[:500]}")
            return []
