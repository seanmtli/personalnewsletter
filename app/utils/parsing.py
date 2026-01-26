"""Shared parsing utilities for JSON and datetime handling."""
import json
import re
from datetime import datetime, timezone
from typing import Optional


def extract_json_from_text(text: str, expect_array: bool = True) -> str:
    """Extract JSON from text that may contain markdown code blocks or extra content.

    Args:
        text: Raw text that may contain JSON
        expect_array: If True, look for array brackets; if False, look for object braces

    Returns:
        Cleaned JSON string ready for parsing
    """
    text = text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    else:
        # Find the JSON structure in the text
        if expect_array:
            start_idx = text.find("[")
            end_idx = text.rfind("]")
        else:
            start_idx = text.find("{")
            end_idx = text.rfind("}")

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text = text[start_idx:end_idx + 1]

    return text.strip()


def parse_json_array(text: str) -> list:
    """Parse JSON array from text, handling markdown formatting."""
    cleaned = extract_json_from_text(text, expect_array=True)
    return json.loads(cleaned)


def parse_json_object(text: str) -> dict:
    """Parse JSON object from text, handling markdown formatting."""
    cleaned = extract_json_from_text(text, expect_array=False)
    return json.loads(cleaned)


def parse_datetime(dt_string: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string to timezone-aware datetime.

    Args:
        dt_string: ISO format datetime string, may have 'Z' suffix

    Returns:
        Timezone-aware datetime or None if parsing fails
    """
    if not dt_string:
        return None

    try:
        # Handle 'Z' suffix for UTC
        dt = datetime.fromisoformat(dt_string.replace("Z", "+00:00"))

        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except (ValueError, TypeError):
        return None


def strip_citations(text: str) -> str:
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
