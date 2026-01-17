import pytest
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock

from app.main import app
from app.database import engine, Base
from app.schemas import ContentItem, CuratedNewsletter


@pytest.fixture(autouse=True)
async def setup_database():
    """Create tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def authenticated_client(client):
    """Create authenticated test client."""
    # Register
    await client.post(
        "/auth/api/register",
        json={"email": "test@example.com", "password": "password123"},
    )

    # Login to get token
    response = await client.post(
        "/auth/api/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    token = response.json()["access_token"]

    # Set cookie
    client.cookies.set("access_token", token)
    return client


@pytest.fixture
def mock_curated_content():
    """Mock curated newsletter content."""
    return CuratedNewsletter(
        items=[
            ContentItem(
                headline="Test Story 1",
                summary="Summary of test story 1",
                source_type="article",
                source_name="ESPN",
                url="https://espn.com/1",
                relevance="Relevant to your interests",
            ),
            ContentItem(
                headline="Test Story 2",
                summary="Summary of test story 2",
                source_type="tweet",
                source_name="@SportsReporter",
                url="https://twitter.com/status/123",
                relevance="Breaking news about your team",
            ),
        ],
        generated_at=datetime.now(),
        interests_used=["Dallas Cowboys"],
        provider_used="claude",
    )


@pytest.mark.asyncio
async def test_preferences_requires_auth(client):
    """Test preferences page requires authentication."""
    response = await client.get("/preferences", follow_redirects=False)
    assert response.status_code == 401 or response.status_code == 303


@pytest.mark.asyncio
async def test_add_preference(authenticated_client):
    """Test adding a preference."""
    response = await authenticated_client.post(
        "/preferences/api",
        json={
            "interest_type": "team",
            "interest_name": "Dallas Cowboys",
            "interest_data": {"league": "NFL"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["interest_name"] == "Dallas Cowboys"


@pytest.mark.asyncio
async def test_get_preferences(authenticated_client):
    """Test getting preferences."""
    # Add a preference first
    await authenticated_client.post(
        "/preferences/api",
        json={
            "interest_type": "team",
            "interest_name": "Dallas Cowboys",
        },
    )

    response = await authenticated_client.get("/preferences/api")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["interest_name"] == "Dallas Cowboys"


@pytest.mark.asyncio
async def test_delete_preference(authenticated_client):
    """Test deleting a preference."""
    # Add a preference
    add_response = await authenticated_client.post(
        "/preferences/api",
        json={
            "interest_type": "team",
            "interest_name": "Dallas Cowboys",
        },
    )
    pref_id = add_response.json()["id"]

    # Delete it
    response = await authenticated_client.delete(f"/preferences/api/{pref_id}")
    assert response.status_code == 200

    # Verify it's gone
    get_response = await authenticated_client.get("/preferences/api")
    assert len(get_response.json()) == 0


@pytest.mark.asyncio
async def test_bulk_update_preferences(authenticated_client):
    """Test bulk updating preferences."""
    response = await authenticated_client.put(
        "/preferences/api/bulk",
        json={
            "preferences": [
                {"interest_type": "team", "interest_name": "Dallas Cowboys"},
                {"interest_type": "athlete", "interest_name": "Dak Prescott"},
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_generate_newsletter_no_preferences(authenticated_client):
    """Test generating newsletter without preferences fails."""
    response = await authenticated_client.post("/newsletter/generate")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_generate_newsletter(authenticated_client, mock_curated_content):
    """Test generating newsletter with preferences."""
    # Add preference
    await authenticated_client.put(
        "/preferences/api/bulk",
        json={
            "preferences": [
                {"interest_type": "team", "interest_name": "Dallas Cowboys"},
            ]
        },
    )

    # Mock the curator
    with patch("app.routers.newsletter.ContentCurator") as MockCurator:
        mock_instance = AsyncMock()
        mock_instance.curate.return_value = mock_curated_content
        MockCurator.return_value = mock_instance

        response = await authenticated_client.post("/newsletter/generate")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "generated"
        assert data["items_count"] == 2
        assert data["provider_used"] == "claude"


@pytest.mark.asyncio
async def test_newsletter_archive(authenticated_client, mock_curated_content):
    """Test newsletter archive page."""
    # Add preference and generate newsletter
    await authenticated_client.put(
        "/preferences/api/bulk",
        json={
            "preferences": [
                {"interest_type": "team", "interest_name": "Dallas Cowboys"},
            ]
        },
    )

    with patch("app.routers.newsletter.ContentCurator") as MockCurator:
        mock_instance = AsyncMock()
        mock_instance.curate.return_value = mock_curated_content
        MockCurator.return_value = mock_instance

        await authenticated_client.post("/newsletter/generate")

    # Check archive
    response = await authenticated_client.get("/newsletter/archive")
    assert response.status_code == 200
    assert "Newsletter" in response.text or "archive" in response.text.lower()


@pytest.mark.asyncio
async def test_get_teams_data(client):
    """Test getting teams data."""
    response = await client.get("/preferences/api/teams")
    assert response.status_code == 200
    data = response.json()
    # Should have NFL teams
    assert "nfl" in data


@pytest.mark.asyncio
async def test_get_athletes_data(client):
    """Test getting athletes data."""
    response = await client.get("/preferences/api/athletes")
    assert response.status_code == 200
    data = response.json()
    # Should have NFL athletes
    assert "nfl" in data
