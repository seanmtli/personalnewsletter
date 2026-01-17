from abc import ABC, abstractmethod
from app.schemas import ContentItem


class ContentProvider(ABC):
    """Abstract base class for content providers."""

    @abstractmethod
    async def fetch_content(self, interests: list[str]) -> list[ContentItem]:
        """
        Fetch content items based on user interests.

        Args:
            interests: List of teams, players, or topics the user follows

        Returns:
            List of ContentItem objects
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and tracking."""
        pass
