import feedparser
from datetime import datetime
from app.services.content.base import ContentProvider
from app.schemas import ContentItem

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
        for feed_name, feed_url in feeds_to_fetch.items():
            try:
                items = await self._fetch_feed(feed_url, interests)
                all_items.extend(items)
            except Exception as e:
                print(f"Error fetching {feed_name} feed: {e}")

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
        feed = feedparser.parse(feed_url)
        items = []

        interests_lower = [i.lower() for i in interests]

        for entry in feed.entries[:20]:  # Check top 20 entries
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            link = entry.get("link", "")

            # Check if entry matches any interest
            entry_text = f"{title} {summary}".lower()
            matching_interests = [i for i in interests_lower if i in entry_text]

            if matching_interests:
                # Parse published date
                published_at = None
                if entry.get("published_parsed"):
                    try:
                        published_at = datetime(*entry.published_parsed[:6])
                    except (ValueError, TypeError):
                        pass

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
                    relevance=f"Matches your interest in {', '.join(matching_interests)}",
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
