"""Screenshot service for generating tweet/reddit post images."""

import re
import httpx
from app.config import get_settings

settings = get_settings()


class ScreenshotService:
    """Generate screenshots of tweets and reddit posts."""

    def __init__(self):
        self.twittershots_api_key = settings.twittershots_api_key

    def extract_tweet_id(self, url: str) -> str | None:
        """Extract tweet ID from a Twitter/X URL."""
        # Match patterns like:
        # https://twitter.com/user/status/1234567890
        # https://x.com/user/status/1234567890
        patterns = [
            r"(?:twitter\.com|x\.com)/\w+/status/(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def extract_author_handle(self, url: str) -> str | None:
        """Extract @username from a Twitter/X URL."""
        patterns = [
            r"(?:twitter\.com|x\.com)/(\w+)/status/",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return f"@{match.group(1)}"
        return None

    async def get_tweet_screenshot(self, tweet_url: str) -> str | None:
        """
        Generate screenshot URL for a tweet.

        Uses TwitterShots API if configured. Returns None if:
        - No API key configured
        - API call fails
        - Invalid tweet URL
        """
        if not self.twittershots_api_key:
            return None

        tweet_id = self.extract_tweet_id(tweet_url)
        if not tweet_id:
            return None

        try:
            async with httpx.AsyncClient() as client:
                # TwitterShots API - returns image directly
                response = await client.get(
                    f"https://api.twittershots.com/api/v1/screenshot/{tweet_id}",
                    params={
                        "format": "png",
                        "theme": "light",
                    },
                    headers={
                        "X-API-KEY": self.twittershots_api_key,
                        "Accept": "image/png",
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    # TwitterShots returns the image directly
                    # We need to use the URL directly for embedding in emails
                    # The API URL with key can be used as the image source
                    return f"https://api.twittershots.com/api/v1/screenshot/{tweet_id}?format=png&theme=light&apiKey={self.twittershots_api_key}"
                else:
                    print(f"TwitterShots API error: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            print(f"Screenshot service error: {e}")
            return None

    async def get_reddit_screenshot(self, reddit_url: str) -> str | None:
        """
        Generate screenshot URL for a reddit post.

        Reddit screenshots are more complex and may require a different service.
        For now, returns None - reddit posts will use the fallback HTML card.
        """
        # Reddit screenshot APIs are less common and more expensive
        # Could integrate with screenshot services like ScreenshotOne in the future
        return None
