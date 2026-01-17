# Personal Sports Newsletter

AI-curated weekly sports newsletter using Claude with web search.

## Quick Start

```bash
# Setup
cd personalnewsletter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run development server
uvicorn app.main:app --reload

# Open http://localhost:8000
```

## Project Structure

```
personalnewsletter/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Settings management
│   ├── database.py          # SQLite/SQLAlchemy setup
│   ├── models.py            # User, Preference, Newsletter models
│   ├── schemas.py           # Pydantic schemas
│   ├── routers/
│   │   ├── auth.py          # Login/register endpoints
│   │   ├── preferences.py   # Interest management
│   │   └── newsletter.py    # Newsletter generation/viewing
│   ├── services/
│   │   ├── content/         # Content providers
│   │   │   ├── claude.py    # Claude API with web search
│   │   │   ├── perplexity.py # Perplexity fallback
│   │   │   └── rss.py       # RSS fallback
│   │   ├── curator.py       # Provider orchestration
│   │   └── emailer.py       # Email sending
│   ├── static/              # CSS and JS
│   └── templates/           # Jinja2 HTML templates
├── data/
│   ├── teams.json           # Team data with logos
│   └── athletes.json        # Athlete data with photos
├── scripts/
│   └── generate.py          # Cron job script
└── tests/                   # Pytest tests
```

## Key Commands

```bash
# Run server
uvicorn app.main:app --reload

# Run tests
pytest tests/ -v

# Generate newsletter (manual)
python scripts/generate.py --user your@email.com --dry-run

# Generate for all users
python scripts/generate.py
```

## Architecture

1. **Content Sourcing**: Claude API with web search → Perplexity → RSS fallback
2. **Authentication**: JWT tokens stored in httponly cookies
3. **Database**: SQLite with SQLAlchemy async
4. **Templates**: Jinja2 with Tailwind CSS (CDN)

## API Endpoints

### Auth
- `POST /auth/api/register` - Register new user
- `POST /auth/api/login` - Login, returns JWT

### Preferences
- `GET /preferences/api` - List user preferences
- `POST /preferences/api` - Add preference
- `DELETE /preferences/api/{id}` - Remove preference
- `PUT /preferences/api/bulk` - Bulk update preferences

### Newsletter
- `POST /newsletter/generate` - Generate newsletter
- `POST /newsletter/send/{id}` - Send via email
- `GET /newsletter/api/list` - List all newsletters
- `GET /newsletter/api/{id}` - Get newsletter details

## Content Provider Priority

1. **Claude** (primary): Uses web search to find articles, tweets, videos
2. **Perplexity** (backup): Called if Claude fails or finds <3 items
3. **RSS** (fallback): ESPN feeds filtered by user interests

## Environment Variables

Required:
- `ANTHROPIC_API_KEY` - Claude API key with web search

Optional:
- `PERPLEXITY_API_KEY` - Perplexity API key (backup)
- `RESEND_API_KEY` - Resend email API key
- `SECRET_KEY` - JWT signing key (auto-generated for dev)

## Cron Setup

Weekly newsletter generation (Sunday 6 PM):
```bash
0 18 * * 0 cd /path/to/personalnewsletter && .venv/bin/python scripts/generate.py
```
