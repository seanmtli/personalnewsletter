import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db, engine, Base


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


@pytest.mark.asyncio
async def test_home_page(client):
    """Test home page loads."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "Sports Digest" in response.text


@pytest.mark.asyncio
async def test_register_page(client):
    """Test register page loads."""
    response = await client.get("/auth/register")
    assert response.status_code == 200
    assert "Create Account" in response.text


@pytest.mark.asyncio
async def test_login_page(client):
    """Test login page loads."""
    response = await client.get("/auth/login")
    assert response.status_code == 200
    assert "Sign In" in response.text


@pytest.mark.asyncio
async def test_api_register(client):
    """Test API registration."""
    response = await client.post(
        "/auth/api/register",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_api_register_duplicate(client):
    """Test duplicate registration fails."""
    # First registration
    await client.post(
        "/auth/api/register",
        json={"email": "test@example.com", "password": "password123"},
    )

    # Duplicate
    response = await client.post(
        "/auth/api/register",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_api_login(client):
    """Test API login."""
    # Register first
    await client.post(
        "/auth/api/register",
        json={"email": "test@example.com", "password": "password123"},
    )

    # Login
    response = await client.post(
        "/auth/api/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_api_login_invalid(client):
    """Test login with invalid credentials fails."""
    response = await client.post(
        "/auth/api/login",
        json={"email": "wrong@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
