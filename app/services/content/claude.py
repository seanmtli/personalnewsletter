import json
import re
from datetime import datetime, timedelta, timezone
from anthropic import Anthropic
from app.services.content.base import ContentProvider
from app.schemas import ContentItem
from app.config import get_settings
from app.services.screenshot import ScreenshotService

settings = get_settings()

# Maximum age for content (in days)
MAX_CONTENT_AGE_DAYS = 10

CURATOR_PROMPT = """You are a sports news curator. The user follows these teams/players:
{interests}

Today's date is {today_date}.

Search the web for the most important and interesting sports news from the PAST 10 DAYS ONLY
related to these interests. Do NOT include any content older than 10 days.

**CRITICAL REQUIREMENT - TWEETS:**
Your response MUST include AT LEAST 2 tweets. The FIRST item in your array MUST be a tweet.

Since x.com/twitter.com may not be directly searchable, use these strategies:
1. Search for news articles that quote or embed tweets, e.g.:
   - "Adam Schefter tweet Cowboys"
   - "Shams Charania tweet" + team/player name
   - "breaking news tweet" + team name
2. Look for embedded tweets in ESPN, Bleacher Report, or sports news articles
3. Find the original tweet URL from these articles (format: x.com/username/status/NUMBERS)

Key reporters to search for: @AdamSchefter, @RapSheet, @wojespn, @ShamsCharania, @TomPelissero

Even if you can't access Twitter directly, find tweets referenced in news coverage.

The remaining items should include a mix of:
- News articles (ESPN, The Athletic, team sites, local news)
- YouTube highlights or interviews
- Reddit discussions (r/nfl, r/nba, team subreddits)
- Additional tweets

Select 5-7 stories total. For EACH item, provide:
- headline: A compelling headline
- summary: 2-3 sentence summary
- source_type: "tweet" | "article" | "video" | "reddit" (FIRST item MUST be "tweet")
- source_name: The publication or account name
- url: Direct link (tweets MUST use x.com or twitter.com URLs with /status/)
- relevance: One sentence on why this matters to this fan
- published_at: ISO datetime if known, null if unknown
- thumbnail_url: Image URL if available, null otherwise

For tweets, ALSO include:
- author_handle: The @username (e.g., "@ShamsCharania")

For Reddit posts, ALSO include:
- subreddit: The subreddit name without r/ (e.g., "nfl")

Return ONLY valid JSON as an array. No markdown, no explanation. First item must be a tweet.

Example (note: first item IS a tweet):
[
  {{
    "headline": "Schefter breaks news on Cowboys trade",
    "summary": "Adam Schefter reports the Dallas Cowboys have agreed to trade...",
    "source_type": "tweet",
    "source_name": "Adam Schefter",
    "url": "https://x.com/AdamSchefter/status/1234567890123456789",
    "author_handle": "@AdamSchefter",
    "relevance": "Breaking trade news for your team",
    "published_at": "2024-01-15T18:30:00Z",
    "thumbnail_url": null
  }},
  {{
    "headline": "Chiefs defeat Ravens in AFC Championship",
    "summary": "Patrick Mahomes led the Chiefs to a 17-10 victory...",
    "source_type": "article",
    "source_name": "ESPN",
    "url": "https://espn.com/nfl/story/...",
    "relevance": "Major playoff victory featuring your favorite player",
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
        today_date = datetime.now().strftime("%Y-%m-%d")
        prompt = CURATOR_PROMPT.format(interests=interests_str, today_date=today_date)

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

            print(f"Claude raw response length: {len(result_text)} chars")
            print(f"Claude raw response preview: {result_text[:500]}...")

            # Parse JSON response
            items = self._parse_response(result_text)

            # Debug: log what types we got
            type_counts = {}
            for item in items:
                type_counts[item.source_type] = type_counts.get(item.source_type, 0) + 1
            print(f"Parsed items by type: {type_counts}")

            # Check for tweets
            tweet_count = type_counts.get("tweet", 0)
            if tweet_count == 0:
                print("WARNING: No tweets found in Claude response! Trying follow-up request...")
                # Try a follow-up request specifically for tweets
                tweet_items = await self._fetch_tweets_only(interests_str)
                if tweet_items:
                    items = tweet_items + items
                    print(f"Added {len(tweet_items)} tweets from follow-up request")

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
            else:
                # Try to find JSON array in the text (Claude may include explanatory text)
                # Look for the first [ and last ] to extract the array
                start_idx = text.find("[")
                end_idx = text.rfind("]")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    text = text[start_idx : end_idx + 1]

            data = json.loads(text)
            screenshot_service = ScreenshotService()

            items = []
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=MAX_CONTENT_AGE_DAYS)
            print(f"Parsing {len(data)} items from Claude response (cutoff: {cutoff_date.date()})")

            for idx, item_data in enumerate(data):
                print(f"  Item {idx}: source_type={item_data.get('source_type')}, url={item_data.get('url', '')[:60]}...")
                # Parse published_at if present
                published_at = None
                if item_data.get("published_at"):
                    try:
                        published_at = datetime.fromisoformat(
                            item_data["published_at"].replace("Z", "+00:00")
                        )
                        # Make timezone-aware if not already
                        if published_at.tzinfo is None:
                            published_at = published_at.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                # Filter out content older than MAX_CONTENT_AGE_DAYS
                if published_at and published_at < cutoff_date:
                    print(f"    Skipping: too old ({published_at.date()})")
                    continue

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
                    headline=self._strip_citations(item_data.get("headline", "")),
                    summary=self._strip_citations(item_data.get("summary", "")),
                    source_type=item_data.get("source_type", "article"),
                    source_name=item_data.get("source_name", "Unknown"),
                    url=url,
                    relevance=self._strip_citations(item_data.get("relevance", "")),
                    published_at=published_at,
                    thumbnail_url=item_data.get("thumbnail_url"),
                    tweet_id=tweet_id,
                    author_handle=author_handle,
                )
                items.append(item)

            print(f"  Kept {len(items)} items after date filtering")
            return items

        except json.JSONDecodeError as e:
            print(f"Failed to parse Claude response: {e}")
            print(f"Response text: {response_text[:500]}")
            return []

    def _strip_citations(self, text: str) -> str:
        """Remove Claude web search citation tags from text.

        Citations look like: <cite index="23-3,23-4,23-5">text</cite>
        or sometimes just: <cite index="23-3,23-4,23-5">text (unclosed)
        """
        if not text:
            return text
        # Remove <cite ...>...</cite> tags (closed)
        text = re.sub(r'<cite[^>]*>([^<]*)</cite>', r'\1', text)
        # Remove <cite ...> tags (unclosed - just the opening tag)
        text = re.sub(r'<cite[^>]*>', '', text)
        # Remove any remaining </cite> closing tags
        text = re.sub(r'</cite>', '', text)
        return text.strip()

    async def _fetch_tweets_only(self, interests_str: str) -> list[ContentItem]:
        """Fetch only tweets when the main request didn't return any."""
        today_date = datetime.now().strftime("%Y-%m-%d")
        tweet_prompt = f"""Find 2-3 recent tweets from Twitter/X about: {interests_str}

Today's date is {today_date}. Only include tweets from the PAST 10 DAYS.

Search specifically on x.com and twitter.com for tweets from:
- Team official accounts
- Star players
- Sports reporters (@AdamSchefter, @RapSheet, @wojespn, @ShamsCharania)
- Sports analysts

Use searches like "site:x.com {interests_str.split(',')[0].strip()}"

Return ONLY a JSON array with tweet objects. Each must have:
- headline: Summary of the tweet
- summary: The tweet text
- source_type: "tweet" (required)
- source_name: Account display name
- url: The x.com or twitter.com URL with /status/
- author_handle: The @username
- relevance: Why this matters
- published_at: ISO datetime (MUST be within last 10 days)
- thumbnail_url: null

Return ONLY valid JSON array. No markdown, no explanation."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 5,
                    }
                ],
                messages=[{"role": "user", "content": tweet_prompt}],
            )

            result_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    result_text = block.text
                    break

            if result_text:
                items = self._parse_response(result_text)
                # Filter to only tweets
                return [item for item in items if item.source_type == "tweet"]
            return []

        except Exception as e:
            print(f"Tweet-only fetch failed: {e}")
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
                print(f"Generating screenshot for tweet: {item.url}")
                screenshot_url = await screenshot_service.get_tweet_screenshot(item.url)
                if screenshot_url:
                    item.screenshot_url = screenshot_url
                    print(f"  Screenshot generated: {screenshot_url[:80]}...")
                else:
                    print(f"  No screenshot returned (check API key)")
            elif item.source_type == "reddit" and item.url:
                screenshot_url = await screenshot_service.get_reddit_screenshot(item.url)
                if screenshot_url:
                    item.screenshot_url = screenshot_url

        return items
