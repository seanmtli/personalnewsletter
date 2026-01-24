import traceback
from datetime import datetime
from app.schemas import CuratedNewsletter, ContentItem, ProviderDebugResult
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

        errors = []  # Track errors for debugging

        for provider in self.providers:
            try:
                print(f"[CURATOR] Trying {provider.name} provider...")
                items = await provider.fetch_content(interests)

                if len(items) >= MIN_ITEMS_THRESHOLD:
                    provider_used = provider.name
                    print(f"[CURATOR] Success: {len(items)} items from {provider.name}")
                    break
                else:
                    msg = f"{provider.name} returned only {len(items)} items, trying next..."
                    print(f"[CURATOR] {msg}")
                    errors.append(msg)

            except Exception as e:
                error_detail = f"{provider.name} failed: {type(e).__name__}: {str(e)}"
                print(f"[CURATOR] {error_detail}")
                print(f"[CURATOR] Stack trace: {traceback.format_exc()}")
                errors.append(error_detail)
                continue

        # Log summary if no provider worked
        if provider_used == "none":
            print(f"[CURATOR] WARNING: All providers failed or returned insufficient items!")
            print(f"[CURATOR] Errors: {errors}")

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

    async def debug_providers(self, interests: list[str]) -> list[ProviderDebugResult]:
        """
        Test each provider individually and return detailed debug information.

        Args:
            interests: List of interests to test with

        Returns:
            List of ProviderDebugResult with success/failure info for each provider
        """
        results = []

        provider_configs = [
            ("claude", ClaudeProvider, bool(settings.anthropic_api_key)),
            ("perplexity", PerplexityProvider, bool(settings.perplexity_api_key)),
            ("rss", RSSProvider, True),  # RSS is always available
        ]

        for provider_name, provider_class, is_available in provider_configs:
            if not is_available:
                results.append(ProviderDebugResult(
                    provider=provider_name,
                    success=False,
                    items_count=0,
                    error=f"API key not configured for {provider_name}",
                    items=[],
                ))
                continue

            try:
                print(f"[DEBUG] Testing {provider_name} provider...")
                provider = provider_class()
                items = await provider.fetch_content(interests)

                results.append(ProviderDebugResult(
                    provider=provider_name,
                    success=True,
                    items_count=len(items),
                    error=None,
                    items=items[:3],  # Include first 3 items for inspection
                ))
                print(f"[DEBUG] {provider_name}: SUCCESS - {len(items)} items")

            except Exception as e:
                error_detail = f"{type(e).__name__}: {str(e)}"
                stack_trace = traceback.format_exc()
                print(f"[DEBUG] {provider_name}: FAILED - {error_detail}")
                print(f"[DEBUG] Stack trace:\n{stack_trace}")

                results.append(ProviderDebugResult(
                    provider=provider_name,
                    success=False,
                    items_count=0,
                    error=error_detail,
                    items=[],
                ))

        return results

    def get_available_providers(self) -> list[str]:
        """Return list of configured provider names."""
        providers = []
        if settings.anthropic_api_key:
            providers.append("claude")
        if settings.perplexity_api_key:
            providers.append("perplexity")
        providers.append("rss")  # Always available
        return providers
