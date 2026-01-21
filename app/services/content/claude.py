import json
from datetime import datetime
from anthropic import Anthropic
from app.services.content.base import ContentProvider
from app.schemas import ContentItem
from app.config import get_settings
from app.services.screenshot import ScreenshotService

settings = get_settings()

CURATOR_PROMPT = """You are a sports news curator. The user follows these teams/players:
{interests}

Search the web for the most important and interesting sports news from the past week
related to these interests.

IMPORTANT: The FIRST item MUST be a popular tweet from Twitter/X. Search for viral or
high-engagement tweets from:
- Star players on these teams
- Beat reporters covering these teams (e.g., @AdamSchefter, @wojespn, @ShamsCharania)
- Official team accounts
- Sports analysts discussing these interests

The remaining items should include a mix of:
- News articles (ESPN, The Athletic, team sites, local news)
- YouTube highlights or interviews
- Interesting Reddit discussions
- Additional notable tweets

Select the TOP 5-7 stories. For each, provide:
- headline: A compelling headline
- summary: 2-3 sentence summary
- source_type: "article" | "tweet" | "video" | "reddit"
- source_name: The publication or account name
- url: Direct link to the content
- relevance: One sentence on why this matters to this fan
- published_at: ISO datetime if known, null if unknown
- thumbnail_url: Image URL if available, null otherwise

For tweets specifically, also include:
- author_handle: The @username (e.g., "@ShamsCharania")

For Reddit posts, also include:
- subreddit: The subreddit name without r/ (e.g., "nba")

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
  }},
  {{
    "headline": "Shams: Lakers acquire star in blockbuster trade",
    "summary": "Breaking news from Shams Charania...",
    "source_type": "tweet",
    "source_name": "Shams Charania",
    "url": "https://x.com/ShamsCharania/status/1234567890",
    "author_handle": "@ShamsCharania",
    "relevance": "Major trade impacts your team's roster",
    "published_at": "2024-01-15T18:30:00Z",
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

            # Ensure a tweet is the first item
            items = self._ensure_tweet_first(items)

            # Generate screenshots for social content
            items = await self._generate_screenshots(items)

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
            screenshot_service = ScreenshotService()

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

                # Extract tweet metadata from URL if it's a tweet
                url = item_data.get("url", "")
                tweet_id = None
                author_handle = item_data.get("author_handle")

                if item_data.get("source_type") == "tweet" and url:
                    tweet_id = screenshot_service.extract_tweet_id(url)
                    # Use extracted handle as fallback if not in response
                    if not author_handle:
                        author_handle = screenshot_service.extract_author_handle(url)

                item = ContentItem(
                    headline=item_data.get("headline", ""),
                    summary=item_data.get("summary", ""),
                    source_type=item_data.get("source_type", "article"),
                    source_name=item_data.get("source_name", "Unknown"),
                    url=url,
                    relevance=item_data.get("relevance", ""),
                    published_at=published_at,
                    thumbnail_url=item_data.get("thumbnail_url"),
                    tweet_id=tweet_id,
                    author_handle=author_handle,
                )
                items.append(item)

            return items

        except json.JSONDecodeError as e:
            print(f"Failed to parse Claude response: {e}")
            print(f"Response text: {response_text[:500]}")
            return []

    def _ensure_tweet_first(self, items: list[ContentItem]) -> list[ContentItem]:
        """Ensure a tweet is the first item in the list."""
        if not items:
            return items

        # If first item is already a tweet, we're good
        if items[0].source_type == "tweet":
            return items

        # Find the first tweet in the list
        tweet_index = None
        for i, item in enumerate(items):
            if item.source_type == "tweet":
                tweet_index = i
                break

        # If we found a tweet, move it to the front
        if tweet_index is not None:
            tweet = items.pop(tweet_index)
            items.insert(0, tweet)
            print(f"Reordered: moved tweet to first position")

        return items

    async def _generate_screenshots(self, items: list[ContentItem]) -> list[ContentItem]:
        """Generate screenshots for tweets and reddit posts."""
        screenshot_service = ScreenshotService()

        for item in items:
            if item.source_type == "tweet" and item.url:
                screenshot_url = await screenshot_service.get_tweet_screenshot(item.url)
                if screenshot_url:
                    item.screenshot_url = screenshot_url
            elif item.source_type == "reddit" and item.url:
                screenshot_url = await screenshot_service.get_reddit_screenshot(item.url)
                if screenshot_url:
                    item.screenshot_url = screenshot_url

        return items
