from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Preference
from app.schemas import SimpleSignup, SimpleSignupResponse
from app.utils.data import load_teams_data, load_athletes_data

router = APIRouter(prefix="/signup", tags=["signup"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def signup_picker_page(request: Request):
    """Interest picker page - no auth required"""
    teams_data = load_teams_data()
    athletes_data = load_athletes_data()

    return templates.TemplateResponse(
        "signup_picker.html",
        {
            "request": request,
            "teams_data": teams_data,
            "athletes_data": athletes_data,
        },
    )


@router.get("/email", response_class=HTMLResponse)
async def signup_email_page(request: Request):
    """Email entry page"""
    return templates.TemplateResponse(
        "signup_email.html",
        {"request": request},
    )


@router.post("/complete", response_model=SimpleSignupResponse)
async def complete_signup(
    data: SimpleSignup,
    db: AsyncSession = Depends(get_db),
):
    """Create user with preferences - no password required"""
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == data.email)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="This email is already registered. Contact the owner to update your interests."
        )

    # Create user without password
    new_user = User(
        email=data.email,
        hashed_password=None,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()  # Get the user ID

    # Create preferences
    for pref_data in data.preferences:
        new_pref = Preference(
            user_id=new_user.id,
            interest_type=pref_data.interest_type,
            interest_name=pref_data.interest_name,
            interest_data=pref_data.interest_data,
        )
        db.add(new_pref)

    await db.commit()

    return SimpleSignupResponse(
        message="Successfully signed up!",
        email=data.email,
        preferences_count=len(data.preferences),
    )


@router.get("/success", response_class=HTMLResponse)
async def signup_success_page(request: Request):
    """Confirmation page after successful signup"""
    return templates.TemplateResponse(
        "signup_success.html",
        {"request": request},
    )
