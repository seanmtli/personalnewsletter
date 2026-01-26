import feedparser
import httpx
from datetime import datetime, timedelta, timezone
from app.services.content.base import ContentProvider
from app.schemas import ContentItem
from app.constants import MAX_CONTENT_AGE_DAYS

# RSS feed sources for different sports
RSS_FEEDS = {
    "general": "https://www.espn.com/espn/rss/news",
    "nfl": "https://www.espn.com/espn/rss/nfl/news",
    "nba": "https://www.espn.com/espn/rss/nba/news",
    "mlb": "https://www.espn.com/espn/rss/mlb/news",
    "nhl": "https://www.espn.com/espn/rss/nhl/news",
    "soccer": "https://www.espn.com/espn/rss/soccer/news",
}

# Keywords to categorize interests
SPORT_KEYWORDS = {
    "nfl": ["nfl", "football", "patriots", "cowboys", "packers", "chiefs", "49ers", "eagles",
            "bills", "dolphins", "jets", "ravens", "steelers", "bengals", "browns", "texans",
            "colts", "jaguars", "titans", "broncos", "chargers", "raiders", "seahawks",
            "cardinals", "rams", "saints", "buccaneers", "falcons", "panthers", "bears",
            "lions", "vikings", "commanders", "giants", "mahomes", "burrow", "allen"],
    "nba": ["nba", "basketball", "lakers", "celtics", "warriors", "nets", "knicks", "bulls",
            "heat", "bucks", "suns", "clippers", "mavericks", "nuggets", "76ers", "grizzlies",
            "timberwolves", "pelicans", "kings", "thunder", "lebron", "curry", "durant",
            "giannis", "jokic", "doncic", "tatum", "embiid"],
    "mlb": ["mlb", "baseball", "yankees", "red sox", "dodgers", "cubs", "astros", "braves",
            "mets", "phillies", "padres", "mariners", "cardinals", "giants", "rangers",
            "angels", "tigers", "twins", "rays", "brewers", "ohtani", "trout", "judge"],
    "nhl": ["nhl", "hockey", "bruins", "rangers", "maple leafs", "canadiens", "blackhawks",
            "penguins", "capitals", "red wings", "flyers", "avalanche", "lightning",
            "golden knights", "oilers", "flames", "mcdavid", "crosby", "ovechkin"],
    "soccer": ["soccer", "premier league", "la liga", "mls", "manchester united", "liverpool",
               "chelsea", "arsenal", "manchester city", "barcelona", "real madrid", "inter miami",
               "messi", "ronaldo", "haaland", "mbappe"],
}


class RSSProvider(ContentProvider):
    """Fallback content provider using RSS feeds."""

    @property
    def name(self) -> str:
        return "rss"

    async def fetch_content(self, interests: list[str]) -> list[ContentItem]:
        # Determine which feeds to fetch based on interests
        feeds_to_fetch = self._get_relevant_feeds(interests)

        all_items = []
        seen_urls = set()  # Track URLs to avoid duplicates

        for feed_name, feed_url in feeds_to_fetch.items():
            try:
                items = await self._fetch_feed(feed_url, interests)
                for item in items:
                    # Deduplicate by URL
                    if item.url not in seen_urls:
                        seen_urls.add(item.url)
                        all_items.append(item)
            except Exception as e:
                print(f"[RSS] Error fetching {feed_name} feed: {e}")

        print(f"[RSS] Found {len(all_items)} unique items matching {interests}")

        # Sort by relevance (items that match more interests rank higher)
        all_items.sort(key=lambda x: self._relevance_score(x, interests), reverse=True)

        # Return top 7 items
        return all_items[:7]

    def _get_relevant_feeds(self, interests: list[str]) -> dict[str, str]:
        """Determine which RSS feeds to fetch based on user interests."""
        interests_lower = [i.lower() for i in interests]
        feeds = {"general": RSS_FEEDS["general"]}

        for sport, keywords in SPORT_KEYWORDS.items():
            for interest in interests_lower:
                if any(kw in interest for kw in keywords):
                    feeds[sport] = RSS_FEEDS[sport]
                    break

        return feeds

    async def _fetch_feed(self, feed_url: str, interests: list[str]) -> list[ContentItem]:
        """Fetch and parse a single RSS feed."""
        # Use httpx to fetch the feed (handles SSL better than feedparser's default)
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.get(
                feed_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            response.raise_for_status()
            feed = feedparser.parse(response.text)

        items = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=MAX_CONTENT_AGE_DAYS)
        interests_lower = [i.lower() for i in interests]

        for entry in feed.entries[:20]:  # Check top 20 entries
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            link = entry.get("link", "")

            # Parse published date first (for filtering)
            published_at = None
            if entry.get("published_parsed"):
                try:
                    published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    pass

            # Filter out content older than MAX_CONTENT_AGE_DAYS
            if published_at and published_at < cutoff_date:
                continue

            # Check if entry matches any interest
            # Match on individual words from interests (e.g., "Dallas Cowboys" matches "Cowboys")
            entry_text = f"{title} {summary}".lower()
            matching_interests = []
            for interest in interests_lower:
                # Check for full interest match
                if interest in entry_text:
                    matching_interests.append(interest)
                else:
                    # Check for individual word matches (for multi-word interests)
                    words = interest.split()
                    if len(words) > 1:
                        for word in words:
                            if len(word) > 3 and word in entry_text:  # Skip short words
                                matching_interests.append(interest)
                                break

            if matching_interests:
                # Get thumbnail if available
                thumbnail_url = None
                if entry.get("media_thumbnail"):
                    thumbnail_url = entry.media_thumbnail[0].get("url")
                elif entry.get("media_content"):
                    thumbnail_url = entry.media_content[0].get("url")

                item = ContentItem(
                    headline=title,
                    summary=self._clean_summary(summary),
                    source_type="article",
                    source_name="ESPN",
                    url=link,
                    relevance="",
                    published_at=published_at,
                    thumbnail_url=thumbnail_url,
                )
                items.append(item)

        return items

    def _clean_summary(self, summary: str) -> str:
        """Clean HTML and truncate summary."""
        import re

        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", "", summary)
        # Truncate to ~200 chars
        if len(clean) > 200:
            clean = clean[:197] + "..."
        return clean

    def _relevance_score(self, item: ContentItem, interests: list[str]) -> int:
        """Calculate relevance score for sorting."""
        score = 0
        item_text = f"{item.headline} {item.summary}".lower()
        for interest in interests:
            if interest.lower() in item_text:
                score += 1
        return score
