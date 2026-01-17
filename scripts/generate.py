#!/usr/bin/env python3
"""
Newsletter generation script for cron job execution.

Usage:
    python scripts/generate.py              # Generate and send for all users
    python scripts/generate.py --dry-run    # Generate but don't send
    python scripts/generate.py --user EMAIL # Generate for specific user

Cron example (run every Sunday at 6 PM):
    0 18 * * 0 cd /path/to/personalnewsletter && .venv/bin/python scripts/generate.py
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import AsyncSessionLocal, init_db
from app.models import User, Preference, Newsletter
from app.services.curator import ContentCurator
from app.services.emailer import EmailService
from app.config import get_settings
from jinja2 import Environment, FileSystemLoader

settings = get_settings()


async def generate_newsletter_for_user(user: User, preferences: list[Preference], dry_run: bool = False):
    """Generate and optionally send newsletter for a single user."""
    print(f"\n{'='*50}")
    print(f"Processing user: {user.email}")

    if not preferences:
        print("  No preferences set, skipping")
        return None

    interests = [p.interest_name for p in preferences]
    print(f"  Interests: {', '.join(interests[:5])}{'...' if len(interests) > 5 else ''}")

    # Generate content
    curator = ContentCurator()
    try:
        curated_content = await curator.curate(interests)
        print(f"  Found {len(curated_content.items)} items via {curated_content.provider_used}")
    except Exception as e:
        print(f"  Error curating content: {e}")
        return None

    if not curated_content.items:
        print("  No content found, skipping")
        return None

    # Render HTML
    env = Environment(loader=FileSystemLoader("app/templates"))
    template = env.get_template("newsletter_email.html")
    html_content = template.render(
        newsletter_name=settings.newsletter_name,
        items=curated_content.items,
        generated_at=curated_content.generated_at,
        site_url=settings.site_url,
    )

    return {
        "user": user,
        "html": html_content,
        "curated": curated_content,
    }


async def save_newsletter(db, user_id: int, html: str, curated_content):
    """Save newsletter to database."""
    newsletter = Newsletter(
        user_id=user_id,
        content=html,
        content_json=curated_content.model_dump(mode="json"),
        interests_used=curated_content.interests_used,
        provider_used=curated_content.provider_used,
    )
    db.add(newsletter)
    await db.commit()
    await db.refresh(newsletter)
    return newsletter


async def send_newsletter(user_email: str, html: str):
    """Send newsletter via email."""
    email_service = EmailService()
    subject = f"{settings.newsletter_name} - Weekly Digest"
    success = await email_service.send(user_email, subject, html)
    return success


async def main(dry_run: bool = False, target_email: str | None = None):
    """Main entry point for newsletter generation."""
    print(f"Newsletter Generation - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")

    # Initialize database
    await init_db()

    async with AsyncSessionLocal() as db:
        # Get users to process
        if target_email:
            result = await db.execute(
                select(User).where(User.email == target_email, User.is_active == True)
            )
            users = [result.scalar_one_or_none()]
            if not users[0]:
                print(f"User not found: {target_email}")
                return
        else:
            result = await db.execute(
                select(User).where(User.is_active == True)
            )
            users = result.scalars().all()

        print(f"Found {len(users)} user(s) to process")

        success_count = 0
        error_count = 0

        for user in users:
            # Get user preferences
            pref_result = await db.execute(
                select(Preference).where(Preference.user_id == user.id)
            )
            preferences = pref_result.scalars().all()

            # Generate newsletter
            result = await generate_newsletter_for_user(user, preferences, dry_run)

            if result is None:
                error_count += 1
                continue

            # Save to database
            newsletter = await save_newsletter(
                db, user.id, result["html"], result["curated"]
            )
            print(f"  Saved newsletter #{newsletter.id}")

            # Send email if not dry run
            if not dry_run:
                if await send_newsletter(user.email, result["html"]):
                    newsletter.sent_at = datetime.utcnow()
                    await db.commit()
                    print(f"  Sent to {user.email}")
                    success_count += 1
                else:
                    print(f"  Failed to send email")
                    error_count += 1
            else:
                print(f"  [DRY RUN] Would send to {user.email}")
                success_count += 1

    print(f"\n{'='*50}")
    print(f"Complete: {success_count} success, {error_count} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate sports newsletters")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate newsletters but don't send emails",
    )
    parser.add_argument(
        "--user",
        type=str,
        help="Generate for specific user email only",
    )

    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, target_email=args.user))
