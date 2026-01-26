from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    secret_key: str = "dev-secret-key-change-in-production"
    database_url: str = "sqlite+aiosqlite:///./data/newsletter.db"

    # JWT settings
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week

    # AI Providers
    anthropic_api_key: str = ""

    # Screenshot service (TwitterShots)
    twittershots_api_key: str = ""

    # Email - Resend
    resend_api_key: str = ""
    from_email: str = "newsletter@example.com"

    # Optional SMTP settings
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None

    # Newsletter settings
    newsletter_name: str = "Your Sports Digest"
    site_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra fields in .env


@lru_cache
def get_settings() -> Settings:
    return Settings()
