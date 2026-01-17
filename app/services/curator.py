from datetime import datetime
from app.schemas import CuratedNewsletter, ContentItem
from app.services.content.claude import ClaudeProvider
from app.services.content.perplexity import PerplexityProvider
from app.services.content.rss import RSSProvider
from app.config import get_settings

settings = get_settings()

MIN_ITEMS_THRESHOLD = 3  # Minimum items before falling back to next provider


class ContentCurator:
    """
    Orchestrates content providers with fallback logic:
    1. Try Claude with web search
    2. Fall back to Perplexity if Claude fails or returns < 3 items
    3. Fall back to RSS if both fail
    """

    def __init__(self):
        self.providers = []

        # Add providers in priority order
        if settings.anthropic_api_key:
            self.providers.append(ClaudeProvider())
        if settings.perplexity_api_key:
            self.providers.append(PerplexityProvider())
        # RSS is always available as fallback
        self.providers.append(RSSProvider())

    async def curate(self, interests: list[str]) -> CuratedNewsletter:
        """
        Curate content from the best available provider.

        Args:
            interests: List of teams, players, or topics to search for

        Returns:
            CuratedNewsletter with items and metadata
        """
        items: list[ContentItem] = []
        provider_used = "none"

        for provider in self.providers:
            try:
                print(f"Trying {provider.name} provider...")
                items = await provider.fetch_content(interests)

                if len(items) >= MIN_ITEMS_THRESHOLD:
                    provider_used = provider.name
                    print(f"Success: {len(items)} items from {provider.name}")
                    break
                else:
                    print(f"{provider.name} returned only {len(items)} items, trying next...")

            except Exception as e:
                print(f"{provider.name} failed: {e}")
                continue

        # If we still have some items (even if < threshold), use them
        if items and provider_used == "none":
            provider_used = self.providers[-1].name if self.providers else "unknown"

        return CuratedNewsletter(
            items=items,
            generated_at=datetime.utcnow(),
            interests_used=interests,
            provider_used=provider_used,
        )

    async def curate_with_provider(
        self, interests: list[str], provider_name: str
    ) -> CuratedNewsletter:
        """
        Curate content using a specific provider.

        Args:
            interests: List of interests
            provider_name: "claude", "perplexity", or "rss"

        Returns:
            CuratedNewsletter from the specified provider
        """
        provider_map = {
            "claude": ClaudeProvider,
            "perplexity": PerplexityProvider,
            "rss": RSSProvider,
        }

        if provider_name not in provider_map:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider = provider_map[provider_name]()
        items = await provider.fetch_content(interests)

        return CuratedNewsletter(
            items=items,
            generated_at=datetime.utcnow(),
            interests_used=interests,
            provider_used=provider_name,
        )
