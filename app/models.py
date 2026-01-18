from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    preferences: Mapped[list["Preference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    newsletters: Mapped[list["Newsletter"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    interest_type: Mapped[str] = mapped_column(String(50))  # "team", "athlete", "custom"
    interest_name: Mapped[str] = mapped_column(String(255))  # e.g., "Dallas Cowboys"
    interest_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # logo_url, league, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="preferences")


class Newsletter(Base):
    __tablename__ = "newsletters"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)  # HTML content
    content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Structured content
    interests_used: Mapped[list | None] = mapped_column(JSON, nullable=True)
    provider_used: Mapped[str] = mapped_column(String(50))  # "claude", "perplexity", "rss"
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="newsletters")
