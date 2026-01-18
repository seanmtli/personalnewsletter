# Personal Sports Newsletter

An AI-curated weekly sports newsletter that delivers personalized content about your favorite teams and athletes.

## Features

- **Simple Signup**: Pick your teams and athletes, enter your email - no password required
- **AI-Curated Content**: Claude searches the web for the best articles, tweets, and highlights
- **Multi-Sport Support**: NFL, NBA, MLB, NHL, Premier League, MLS, and more
- **Weekly Digest**: 5-7 top stories delivered to your inbox every week

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite with SQLAlchemy (async)
- **Frontend**: Jinja2 templates with Tailwind CSS
- **AI**: Claude API with web search
- **Email**: Resend or SMTP

## Quick Start

### Prerequisites

- Python 3.11+
- Anthropic API key (with web search enabled)

### Installation

```bash
# Clone the repository
git clone https://github.com/seanmtli/personalnewsletter.git
cd personalnewsletter

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Edit `.env` with your settings:

```env
# Required
ANTHROPIC_API_KEY=your_anthropic_api_key

# Optional - for sending emails
RESEND_API_KEY=your_resend_api_key
# OR use SMTP
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your_email
SMTP_PASSWORD=your_password
```

### Running the Server

```bash
uvicorn app.main:app --reload
```

Visit http://localhost:8000 to get started.

## User Flow

1. **Home**: Landing page with "Get Started" button
2. **Pick Interests**: Select teams and athletes from NFL, NBA, MLB, NHL, and soccer leagues
3. **Enter Email**: Provide email address (no password needed)
4. **Confirmation**: Success page with next steps

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
│   │   ├── auth.py          # Login/register (admin use)
│   │   ├── preferences.py   # Interest management
│   │   ├── newsletter.py    # Newsletter generation/viewing
│   │   └── signup.py        # Simplified signup flow
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

## Newsletter Generation

### Manual Generation

```bash
# Generate for a specific user (dry run)
python scripts/generate.py --user your@email.com --dry-run

# Generate and send
python scripts/generate.py --user your@email.com

# Generate for all users
python scripts/generate.py
```

### Automated (Cron)

Set up weekly generation (e.g., Sunday 6 PM):

```bash
0 18 * * 0 cd /path/to/personalnewsletter && .venv/bin/python scripts/generate.py
```

## API Endpoints

### Signup (Public)
- `GET /signup` - Interest picker page
- `GET /signup/email` - Email entry page
- `POST /signup/complete` - Create user with preferences
- `GET /signup/success` - Confirmation page

### Preferences (Authenticated)
- `GET /preferences` - Preferences management page
- `GET /preferences/api` - List user preferences
- `PUT /preferences/api/bulk` - Bulk update preferences

### Newsletter (Authenticated)
- `POST /newsletter/generate` - Generate newsletter
- `POST /newsletter/send/{id}` - Send via email
- `GET /newsletter/api/list` - List all newsletters
- `GET /newsletter/api/{id}` - Get newsletter details

## Content Provider Priority

1. **Claude** (primary): Uses web search to find articles, tweets, videos
2. **Perplexity** (backup): Called if Claude fails or finds <3 items
3. **RSS** (fallback): ESPN feeds filtered by user interests

## License

MIT
