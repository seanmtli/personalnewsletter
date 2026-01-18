from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import init_db
from app.routers import auth, preferences, newsletter, signup
from app.routers.auth import get_current_user, get_db
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database
    await init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Personal Sports Newsletter",
    description="AI-curated weekly sports digest",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(auth.router)
app.include_router(preferences.router)
app.include_router(newsletter.router)
app.include_router(signup.router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Check if user is logged in
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select
    from app.models import Preference, Newsletter
    from app.database import AsyncSessionLocal

    # Check authentication
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/auth/login", status_code=303)

    async with AsyncSessionLocal() as db:
        try:
            user = await get_current_user(request, db)
        except Exception:
            return RedirectResponse(url="/auth/login", status_code=303)

        # Get user's preferences count
        pref_result = await db.execute(
            select(Preference).where(Preference.user_id == user.id)
        )
        preferences = pref_result.scalars().all()

        # Get recent newsletters
        newsletter_result = await db.execute(
            select(Newsletter)
            .where(Newsletter.user_id == user.id)
            .order_by(Newsletter.created_at.desc())
            .limit(5)
        )
        recent_newsletters = newsletter_result.scalars().all()

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "preferences": preferences,
                "recent_newsletters": recent_newsletters,
            },
        )


# Health check endpoint
@app.get("/health")
async def health():
    return {"status": "healthy"}
