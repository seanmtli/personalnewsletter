import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models import User, Preference
from app.schemas import PreferenceCreate, PreferenceResponse, PreferenceBulkUpdate
from app.routers.auth import get_current_user

router = APIRouter(prefix="/preferences", tags=["preferences"])
templates = Jinja2Templates(directory="app/templates")


def load_teams_data() -> dict:
    teams_path = Path("data/teams.json")
    if teams_path.exists():
        with open(teams_path) as f:
            return json.load(f)
    return {}


def load_athletes_data() -> dict:
    athletes_path = Path("data/athletes.json")
    if athletes_path.exists():
        with open(athletes_path) as f:
            return json.load(f)
    return {}


@router.get("", response_class=HTMLResponse)
async def preferences_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Load user's current preferences
    result = await db.execute(
        select(Preference).where(Preference.user_id == current_user.id)
    )
    user_preferences = result.scalars().all()

    # Load teams and athletes data
    teams_data = load_teams_data()
    athletes_data = load_athletes_data()

    return templates.TemplateResponse(
        "preferences.html",
        {
            "request": request,
            "user": current_user,
            "preferences": user_preferences,
            "teams_data": teams_data,
            "athletes_data": athletes_data,
        },
    )


@router.get("/api", response_model=list[PreferenceResponse])
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Preference).where(Preference.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/api", response_model=PreferenceResponse)
async def add_preference(
    preference: PreferenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if this preference already exists
    result = await db.execute(
        select(Preference).where(
            Preference.user_id == current_user.id,
            Preference.interest_name == preference.interest_name,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Interest already added")

    new_pref = Preference(
        user_id=current_user.id,
        interest_type=preference.interest_type,
        interest_name=preference.interest_name,
        interest_data=preference.interest_data,
    )
    db.add(new_pref)
    await db.commit()
    await db.refresh(new_pref)
    return new_pref


@router.delete("/api/{preference_id}")
async def delete_preference(
    preference_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Preference).where(
            Preference.id == preference_id,
            Preference.user_id == current_user.id,
        )
    )
    pref = result.scalar_one_or_none()
    if not pref:
        raise HTTPException(status_code=404, detail="Preference not found")

    await db.delete(pref)
    await db.commit()
    return {"status": "deleted"}


@router.put("/api/bulk", response_model=list[PreferenceResponse])
async def bulk_update_preferences(
    data: PreferenceBulkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Delete all existing preferences
    await db.execute(
        delete(Preference).where(Preference.user_id == current_user.id)
    )

    # Add new preferences
    new_prefs = []
    for pref_data in data.preferences:
        new_pref = Preference(
            user_id=current_user.id,
            interest_type=pref_data.interest_type,
            interest_name=pref_data.interest_name,
            interest_data=pref_data.interest_data,
        )
        db.add(new_pref)
        new_prefs.append(new_pref)

    await db.commit()

    # Refresh all preferences
    for pref in new_prefs:
        await db.refresh(pref)

    return new_prefs


@router.get("/api/teams")
async def get_teams():
    return load_teams_data()


@router.get("/api/athletes")
async def get_athletes():
    return load_athletes_data()
