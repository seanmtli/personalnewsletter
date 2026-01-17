import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from app.schemas import ContentItem, CuratedNewsletter
from app.services.curator import ContentCurator
from app.services.content.rss import RSSProvider


@pytest.fixture
def sample_content_items():
    """Sample content items for testing."""
    return [
        ContentItem(
            headline="Chiefs Win Super Bowl",
            summary="Kansas City Chiefs defeat the 49ers in overtime.",
            source_type="article",
            source_name="ESPN",
            url="https://espn.com/article/1",
            relevance="Major victory for your team",
            published_at=datetime.now(),
            thumbnail_url=None,
        ),
        ContentItem(
            headline="Mahomes Named MVP",
            summary="Patrick Mahomes wins his third Super Bowl MVP.",
            source_type="article",
            source_name="NFL.com",
            url="https://nfl.com/article/2",
            relevance="Your favorite player wins big award",
            published_at=datetime.now(),
            thumbnail_url=None,
        ),
        ContentItem(
            headline="Chiefs Parade Highlights",
            summary="Millions celebrate in Kansas City.",
            source_type="video",
            source_name="YouTube",
            url="https://youtube.com/watch?v=abc",
            relevance="Team celebration coverage",
            published_at=datetime.now(),
            thumbnail_url=None,
        ),
    ]


@pytest.mark.asyncio
async def test_curator_with_mock_claude(sample_content_items):
    """Test curator with mocked Claude provider."""
    with patch("app.services.curator.ClaudeProvider") as MockClaude:
        mock_instance = AsyncMock()
        mock_instance.fetch_content.return_value = sample_content_items
        mock_instance.name = "claude"
        MockClaude.return_value = mock_instance

        # Temporarily set API key
        with patch("app.services.curator.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.perplexity_api_key = ""

            curator = ContentCurator()
            curator.providers = [mock_instance]

            result = await curator.curate(["Kansas City Chiefs", "Patrick Mahomes"])

            assert isinstance(result, CuratedNewsletter)
            assert len(result.items) == 3
            assert result.provider_used == "claude"
            assert "Kansas City Chiefs" in result.interests_used


@pytest.mark.asyncio
async def test_curator_fallback():
    """Test curator falls back when primary provider fails."""
    with patch("app.services.curator.ClaudeProvider") as MockClaude, \
         patch("app.services.curator.RSSProvider") as MockRSS:

        # Claude fails
        mock_claude = AsyncMock()
        mock_claude.fetch_content.side_effect = Exception("API Error")
        mock_claude.name = "claude"
        MockClaude.return_value = mock_claude

        # RSS succeeds
        mock_rss = AsyncMock()
        mock_rss.fetch_content.return_value = [
            ContentItem(
                headline="RSS Article",
                summary="From RSS feed",
                source_type="article",
                source_name="ESPN RSS",
                url="https://espn.com/rss/1",
                relevance="Matches your interest",
            )
        ]
        mock_rss.name = "rss"
        MockRSS.return_value = mock_rss

        with patch("app.services.curator.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.perplexity_api_key = ""

            curator = ContentCurator()
            curator.providers = [mock_claude, mock_rss]

            result = await curator.curate(["Dallas Cowboys"])

            assert len(result.items) == 1
            assert result.provider_used == "rss"


def test_rss_provider_get_relevant_feeds():
    """Test RSS provider selects correct feeds."""
    provider = RSSProvider()

    # NFL interests
    feeds = provider._get_relevant_feeds(["Dallas Cowboys", "Patrick Mahomes"])
    assert "nfl" in feeds

    # NBA interests
    feeds = provider._get_relevant_feeds(["Los Angeles Lakers", "LeBron James"])
    assert "nba" in feeds

    # Multiple sports
    feeds = provider._get_relevant_feeds(["Cowboys", "Lakers", "Yankees"])
    assert "nfl" in feeds
    assert "nba" in feeds
    assert "mlb" in feeds


def test_content_item_schema():
    """Test ContentItem schema validation."""
    item = ContentItem(
        headline="Test Headline",
        summary="Test summary",
        source_type="article",
        source_name="Test Source",
        url="https://example.com",
        relevance="Test relevance",
    )

    assert item.headline == "Test Headline"
    assert item.source_type == "article"
    assert item.published_at is None
    assert item.thumbnail_url is None


def test_curated_newsletter_schema(sample_content_items):
    """Test CuratedNewsletter schema."""
    newsletter = CuratedNewsletter(
        items=sample_content_items,
        generated_at=datetime.now(),
        interests_used=["Chiefs", "Mahomes"],
        provider_used="claude",
    )

    assert len(newsletter.items) == 3
    assert newsletter.provider_used == "claude"
    assert "Chiefs" in newsletter.interests_used
