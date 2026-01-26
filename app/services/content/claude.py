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

# Models - using Claude 3.5 Haiku for cost efficiency
SEARCH_MODEL = "claude-3-5-haiku-20241022"  # Cheapest model with web search
VERIFY_MODEL = "claude-3-5-haiku-20241022"  # Cheapest model for verification

SEARCH_PROMPT = """You are a sports news curator. Find 7-10 recent news items for someone who follows:
{interests}

Today is {date}. Only include content from the PAST 10 DAYS.

## CRITICAL RELEVANCE RULES
Each item MUST be DIRECTLY about one of the listed interests:
- If the interest is "Dallas Cowboys" → article must be primarily about the Cowboys
- If the interest is "Patrick Mahomes" → article must feature Mahomes as a main subject
- Do NOT include items where the interest is only briefly mentioned
- Do NOT include general league news unless it directly impacts an interest

## Content Types to Search For
- Breaking news and analysis articles from any sports publication
- Social media posts from players, teams, coaches, or reporters covering these interests
- Video highlights, interviews, or press conferences
- Reddit discussions in team/player subreddits

## For Each Item Provide
- headline: Compelling title
- summary: 2-3 sentence summary
- source_type: "article" | "tweet" | "video" | "reddit"
- source_name: Publication or account name
- url: Direct link
- relevance: Which interest this relates to AND why it matters
- published_at: ISO datetime
- thumbnail_url: Image URL if available
- author_handle: @username for social posts (tweets)
- subreddit: subreddit name without r/ (for reddit posts)

Return ONLY a valid JSON array. No markdown, no explanation.
"""

VERIFY_PROMPT = """You are a relevance verification agent. Review these news items for a user who follows:
{interests}

## Your Task
For each item, determine if it is DIRECTLY relevant to the user's interests.

## Scoring Criteria (1-10)
- 10: Article is entirely about one of their interests (e.g., "Cowboys sign new QB")
- 7-9: Interest is a primary subject of the article
- 4-6: Interest is mentioned but not the main focus
- 1-3: Interest is barely mentioned or tangentially related

## Rules
- REJECT (score < 7) items where the interest is only briefly mentioned
- REJECT generic league news that doesn't specifically feature their interests
- KEEP items that would genuinely excite a fan of that specific team/player

## Input Items
{items_json}

## Output
Return a JSON object with ONLY the items scoring 7+, adding a "relevance_score" field to each.
If fewer than 3 items pass, note this in a "quality_warning" field.

Return ONLY valid JSON. Format:
{{
  "verified_items": [...],
  "rejected_count": N,
  "quality_warning": "optional message if < 3 items passed"
}}
"""


class ClaudeProvider(ContentProvider):
    """Content provider using Claude API with web search."""

    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)

    @property
    def name(self) -> str:
        return "claude"

    async def fetch_content(self, interests: list[str]) -> list[ContentItem]:
        """Fetch and verify content using two-stage architecture."""
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key not configured")

        # Stage 1: Search for content using Opus
        raw_items = await self._search_for_content(interests)

        if not raw_items:
            print("[CLAUDE] No items found in search stage")
            return []

        print(f"[CLAUDE] Search stage found {len(raw_items)} items")

        # Stage 2: Verify relevance using Sonnet
        verified_items = await self._verify_relevance(raw_items, interests)

        # If verification filtered too aggressively, log warning
        if len(verified_items) < 3 and len(raw_items) >= 3:
            print(f"[CLAUDE] Warning: Verification filtered {len(raw_items)} → {len(verified_items)} items")

        # Generate screenshots for social content
        verified_items = await self._generate_screenshots(verified_items)

        return verified_items

    async def _search_for_content(self, interests: list[str]) -> list[ContentItem]:
        """Stage 1: Search for content using Opus with web search."""
        interests_str = ", ".join(interests)
        today_date = datetime.now().strftime("%Y-%m-%d")
        prompt = SEARCH_PROMPT.format(interests=interests_str, date=today_date)

        try:
            print(f"[CLAUDE] Searching with {SEARCH_MODEL}...")
            response = self.client.messages.create(
                model=SEARCH_MODEL,
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

            print(f"[CLAUDE] Search response length: {len(result_text)} chars")
            print(f"[CLAUDE] Search response preview: {result_text[:500]}...")

            # Parse JSON response
            items = self._parse_response(result_text)

            # Debug: log what types we got
            type_counts = {}
            for item in items:
                type_counts[item.source_type] = type_counts.get(item.source_type, 0) + 1
            print(f"[CLAUDE] Parsed items by type: {type_counts}")

            return items

        except Exception as e:
            print(f"[CLAUDE] Search error: {e}")
            raise

    async def _verify_relevance(self, items: list[ContentItem], interests: list[str]) -> list[ContentItem]:
        """Stage 2: Verify relevance of items using Sonnet."""
        if not items:
            return []

        interests_str = ", ".join(interests)

        # Convert items to JSON for verification
        items_data = []
        for item in items:
            items_data.append({
                "headline": item.headline,
                "summary": item.summary,
                "source_type": item.source_type,
                "source_name": item.source_name,
                "url": item.url,
                "relevance": item.relevance,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "thumbnail_url": item.thumbnail_url,
                "author_handle": item.author_handle,
            })

        items_json = json.dumps(items_data, indent=2)
        prompt = VERIFY_PROMPT.format(interests=interests_str, items_json=items_json)

        try:
            print(f"[CLAUDE] Verifying {len(items)} items with {VERIFY_MODEL}...")
            response = self.client.messages.create(
                model=VERIFY_MODEL,
                max_tokens=4096,
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

            # Parse verification response
            print(f"[CLAUDE] Verification response preview: {result_text[:500]}...")
            verified_data = self._parse_verification_response(result_text)

            if verified_data.get("quality_warning"):
                print(f"[CLAUDE] Quality warning: {verified_data['quality_warning']}")

            rejected_count = verified_data.get("rejected_count", 0)
            if rejected_count > 0:
                print(f"[CLAUDE] Verification rejected {rejected_count} items")

            # Convert verified items back to ContentItem objects
            verified_items = []
            screenshot_service = ScreenshotService()

            for item_data in verified_data.get("verified_items", []):
                # Parse published_at if present
                published_at = None
                if item_data.get("published_at"):
                    try:
                        published_at = datetime.fromisoformat(
                            item_data["published_at"].replace("Z", "+00:00")
                        )
                        if published_at.tzinfo is None:
                            published_at = published_at.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                # Extract tweet metadata
                url = item_data.get("url", "")
                tweet_id = None
                author_handle = item_data.get("author_handle")

                if item_data.get("source_type") == "tweet" and url:
                    tweet_id = screenshot_service.extract_tweet_id(url)
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
                verified_items.append(item)

            print(f"[CLAUDE] Verification passed {len(verified_items)} items")
            return verified_items

        except Exception as e:
            print(f"[CLAUDE] Verification error: {e}, returning unverified items")
            # On verification failure, return original items
            return items

    def _parse_verification_response(self, response_text: str) -> dict:
        """Parse the verification agent's JSON response."""
        try:
            text = response_text.strip()

            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            else:
                # Find JSON object
                start_idx = text.find("{")
                end_idx = text.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    text = text[start_idx:end_idx + 1]

            return json.loads(text)

        except json.JSONDecodeError as e:
            print(f"[CLAUDE] Failed to parse verification response: {e}")
            return {"verified_items": [], "rejected_count": 0}

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
            print(f"[CLAUDE] Parsing {len(data)} items (cutoff: {cutoff_date.date()})")

            for idx, item_data in enumerate(data):
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
                    print(f"[CLAUDE]   Item {idx}: Skipping (too old: {published_at.date()})")
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

            print(f"[CLAUDE]   Kept {len(items)} items after date filtering")
            return items

        except json.JSONDecodeError as e:
            print(f"[CLAUDE] Failed to parse response: {e}")
            print(f"[CLAUDE] Response text: {response_text[:500]}")
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

    async def _generate_screenshots(self, items: list[ContentItem]) -> list[ContentItem]:
        """Generate screenshots for tweets and reddit posts."""
        screenshot_service = ScreenshotService()

        for item in items:
            if item.source_type == "tweet" and item.url:
                print(f"[CLAUDE] Generating screenshot for tweet: {item.url}")
                screenshot_url = await screenshot_service.get_tweet_screenshot(item.url)
                if screenshot_url:
                    item.screenshot_url = screenshot_url
                    print(f"[CLAUDE]   Screenshot generated: {screenshot_url[:80]}...")
                else:
                    print(f"[CLAUDE]   No screenshot returned (check API key)")
            elif item.source_type == "reddit" and item.url:
                screenshot_url = await screenshot_service.get_reddit_screenshot(item.url)
                if screenshot_url:
                    item.screenshot_url = screenshot_url

        return items
