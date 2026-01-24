import json
from datetime import datetime, timedelta, timezone
from openai import OpenAI
from app.services.content.base import ContentProvider
from app.schemas import ContentItem
from app.config import get_settings

settings = get_settings()

# Maximum age for content (in days)
MAX_CONTENT_AGE_DAYS = 10

CURATOR_PROMPT = """You are a sports news curator. The user follows these teams/players:
{interests}

Today's date is {today_date}.

Find the most important and interesting sports news from the PAST 10 DAYS ONLY related to these interests.
Do NOT include any content older than 10 days.
Look for content from news articles, social media, YouTube, and Reddit.

Select the TOP 5-7 stories and return them as a JSON array. Each item should have:
- headline: A compelling headline
- summary: 2-3 sentence summary
- source_type: "article" | "tweet" | "video" | "reddit"
- source_name: The publication or account name
- url: Direct link to the content
- relevance: One sentence on why this matters to this fan
- published_at: ISO datetime (MUST be within the last 10 days)
- thumbnail_url: Image URL if available, null otherwise

Return ONLY valid JSON as an array. No other text or explanation."""


class PerplexityProvider(ContentProvider):
    """Content provider using Perplexity API (OpenAI-compatible)."""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.perplexity_api_key,
            base_url="https://api.perplexity.ai",
        )

    @property
    def name(self) -> str:
        return "perplexity"

    async def fetch_content(self, interests: list[str]) -> list[ContentItem]:
        if not settings.perplexity_api_key:
            raise ValueError("Perplexity API key not configured")

        interests_str = ", ".join(interests)
        today_date = datetime.now().strftime("%Y-%m-%d")
        prompt = CURATOR_PROMPT.format(interests=interests_str, today_date=today_date)

        try:
            response = self.client.chat.completions.create(
                model="sonar",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a sports news curator. Return only valid JSON. Only include content from the past 10 days.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            )

            result_text = response.choices[0].message.content
            items = self._parse_response(result_text)
            return items

        except Exception as e:
            print(f"Perplexity API error: {e}")
            raise

    def _parse_response(self, response_text: str) -> list[ContentItem]:
        """Parse Perplexity's JSON response into ContentItem objects."""
        try:
            text = response_text.strip()

            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)

            items = []
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=MAX_CONTENT_AGE_DAYS)
            print(f"[Perplexity] Parsing {len(data)} items (cutoff: {cutoff_date.date()})")

            for item_data in data:
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
                    print(f"  Skipping: too old ({published_at.date()})")
                    continue

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

            print(f"[Perplexity] Kept {len(items)} items after date filtering")
            return items

        except json.JSONDecodeError as e:
            print(f"Failed to parse Perplexity response: {e}")
            return []
