from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Literal


# Auth schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str | None = None


# Preference schemas
class PreferenceCreate(BaseModel):
    interest_type: Literal["team", "athlete", "custom"]
    interest_name: str
    interest_data: dict | None = None


class PreferenceResponse(BaseModel):
    id: int
    interest_type: str
    interest_name: str
    interest_data: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class PreferenceBulkUpdate(BaseModel):
    preferences: list[PreferenceCreate]


# Content/Newsletter schemas
class ContentItem(BaseModel):
    headline: str
    summary: str
    source_type: Literal["article", "tweet", "video", "reddit"]
    source_name: str
    url: str
    relevance: str
    published_at: datetime | None = None
    thumbnail_url: str | None = None
    # Social embed fields
    tweet_id: str | None = None  # Tweet ID extracted from URL
    screenshot_url: str | None = None  # Generated screenshot image URL
    author_handle: str | None = None  # @username for attribution


class CuratedNewsletter(BaseModel):
    items: list[ContentItem]
    generated_at: datetime
    interests_used: list[str]
    provider_used: str


class NewsletterResponse(BaseModel):
    id: int
    content: str
    content_json: dict | None
    interests_used: list | None
    provider_used: str
    sent_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


# Simple signup schemas (no password required)
class SimpleSignup(BaseModel):
    email: EmailStr
    preferences: list[PreferenceCreate]


class SimpleSignupResponse(BaseModel):
    message: str
    email: str
    preferences_count: int


# Test newsletter schema
class TestNewsletterRequest(BaseModel):
    email: EmailStr
    interests: list[str]  # Simple list of interest names like ["Dallas Cowboys", "Patrick Mahomes"]


# Debug endpoint schema
class DebugNewsletterRequest(BaseModel):
    interests: list[str]


class ProviderDebugResult(BaseModel):
    provider: str
    success: bool
    items_count: int
    error: str | None = None
    items: list[ContentItem] = []


class DebugNewsletterResponse(BaseModel):
    providers_available: list[str]
    results: list[ProviderDebugResult]
    recommendation: str
