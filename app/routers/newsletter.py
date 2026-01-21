from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models import User, Preference, Newsletter
from app.schemas import NewsletterResponse, TestNewsletterRequest
from app.routers.auth import get_current_user
from app.services.curator import ContentCurator
from app.services.emailer import EmailService
from app.config import get_settings

router = APIRouter(prefix="/newsletter", tags=["newsletter"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("/archive", response_class=HTMLResponse)
async def archive_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Newsletter)
        .where(Newsletter.user_id == current_user.id)
        .order_by(Newsletter.created_at.desc())
    )
    newsletters = result.scalars().all()

    return templates.TemplateResponse(
        "archive.html",
        {
            "request": request,
            "user": current_user,
            "newsletters": newsletters,
        },
    )


@router.get("/view/{newsletter_id}", response_class=HTMLResponse)
async def view_newsletter(
    newsletter_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Newsletter).where(
            Newsletter.id == newsletter_id,
            Newsletter.user_id == current_user.id,
        )
    )
    newsletter = result.scalar_one_or_none()

    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter not found")

    return templates.TemplateResponse(
        "newsletter_view.html",
        {
            "request": request,
            "user": current_user,
            "newsletter": newsletter,
        },
    )


@router.post("/generate")
async def generate_newsletter(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get user preferences
    result = await db.execute(
        select(Preference).where(Preference.user_id == current_user.id)
    )
    preferences = result.scalars().all()

    if not preferences:
        raise HTTPException(
            status_code=400,
            detail="No preferences set. Please add some interests first.",
        )

    # Extract interest names
    interests = [p.interest_name for p in preferences]

    # Generate newsletter content
    curator = ContentCurator()
    curated_content = await curator.curate(interests)

    # Render HTML content
    newsletter_html = templates.get_template("newsletter_email.html").render(
        newsletter_name=settings.newsletter_name,
        items=curated_content.items,
        generated_at=curated_content.generated_at,
        site_url=settings.site_url,
    )

    # Save to database
    newsletter = Newsletter(
        user_id=current_user.id,
        content=newsletter_html,
        content_json=curated_content.model_dump(mode="json"),
        interests_used=curated_content.interests_used,
        provider_used=curated_content.provider_used,
    )
    db.add(newsletter)
    await db.commit()
    await db.refresh(newsletter)

    return {
        "status": "generated",
        "newsletter_id": newsletter.id,
        "items_count": len(curated_content.items),
        "provider_used": curated_content.provider_used,
    }


@router.post("/test")
async def test_newsletter(
    test_request: TestNewsletterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Quick test: generate and send newsletter with given preferences.
    No auth required - uses email as identifier.
    """
    email = test_request.email
    interests = test_request.interests

    # 1. Get or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(email=email, hashed_password=None, is_active=True)
        db.add(user)
        await db.flush()

    # 2. Clear existing preferences and add new ones
    await db.execute(delete(Preference).where(Preference.user_id == user.id))

    for interest in interests:
        pref = Preference(
            user_id=user.id,
            interest_type="custom",
            interest_name=interest,
        )
        db.add(pref)

    await db.commit()

    # 3. Generate newsletter content
    curator = ContentCurator()
    curated_content = await curator.curate(interests)

    # 4. Render HTML
    newsletter_html = templates.get_template("newsletter_email.html").render(
        newsletter_name=settings.newsletter_name,
        generated_at=curated_content.generated_at,
        items=curated_content.items,
        site_url=settings.site_url,
    )

    # 5. Save to database
    newsletter = Newsletter(
        user_id=user.id,
        content=newsletter_html,
        content_json=curated_content.model_dump(mode="json"),
        interests_used=interests,
        provider_used=curated_content.provider_used,
    )
    db.add(newsletter)
    await db.commit()
    await db.refresh(newsletter)

    # 6. Send email immediately
    email_service = EmailService()
    subject = f"{settings.newsletter_name} - Test"
    sent = await email_service.send(email, subject, newsletter_html)

    return {
        "status": "sent" if sent else "generated_but_not_sent",
        "newsletter_id": newsletter.id,
        "preview_url": f"{settings.site_url}/newsletter/view/{newsletter.id}",
        "provider_used": curated_content.provider_used,
        "items_count": len(curated_content.items),
    }


@router.post("/send/{newsletter_id}")
async def send_newsletter(
    newsletter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if email is configured
    email_configured = (
        (settings.resend_api_key and not settings.resend_api_key.startswith("re_your"))
        or (settings.smtp_host and settings.smtp_user)
    )
    if not email_configured:
        raise HTTPException(
            status_code=400,
            detail="Email not configured. Add RESEND_API_KEY or SMTP settings to .env file.",
        )

    result = await db.execute(
        select(Newsletter).where(
            Newsletter.id == newsletter_id,
            Newsletter.user_id == current_user.id,
        )
    )
    newsletter = result.scalar_one_or_none()

    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter not found")

    # Send email
    email_service = EmailService()
    success = await email_service.send(
        to_email=current_user.email,
        subject=f"{settings.newsletter_name} - Weekly Digest",
        html_content=newsletter.content,
    )

    if success:
        newsletter.sent_at = datetime.utcnow()
        await db.commit()
        return {"status": "sent", "email": current_user.email}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email. Check your API key is valid.")


@router.get("/api/list", response_model=list[NewsletterResponse])
async def list_newsletters(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Newsletter)
        .where(Newsletter.user_id == current_user.id)
        .order_by(Newsletter.created_at.desc())
    )
    return result.scalars().all()


@router.get("/api/{newsletter_id}", response_model=NewsletterResponse)
async def get_newsletter(
    newsletter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Newsletter).where(
            Newsletter.id == newsletter_id,
            Newsletter.user_id == current_user.id,
        )
    )
    newsletter = result.scalar_one_or_none()

    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter not found")

    return newsletter
