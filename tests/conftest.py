"""
Pytest configuration and shared fixtures for NexusGuard tests.
"""

import inspect

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator
import os

os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5432"
os.environ["DB_NAME"] = "cisco_security"
os.environ["DB_USER"] = "cisco_app"
os.environ["DB_PASSWORD"] = "devpassword123"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/1"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/2"

# Configure test database
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:",
)


@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create tables
    from app.infrastructure.database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def test_client(test_db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    from app.main import create_application
    from app.infrastructure.database.session import get_db
    
    app = create_application()

    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def client(test_client):
    """Backward-compatible alias used by existing integration tests."""
    return test_client


@pytest_asyncio.fixture
async def authenticated_client(test_client):
    """Create authenticated test client."""
    # Login with demo credentials
    login_response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    
    if login_response.status_code == 200:
        token = login_response.json().get("access_token")
        test_client.headers["Authorization"] = f"Bearer {token}"
    
    return test_client


@pytest_asyncio.fixture
async def demo_user(test_db_session):
    """Create a demo user for testing."""
    from app.infrastructure.database.models import User
    from app.core.security import hash_password
    
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("TestPass123!"),
        role="analyst",
        is_active=True,
        tenant_id="test-tenant",
    )
    
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    
    return user


@pytest_asyncio.fixture
async def demo_devices(test_db_session, demo_user):
    """Create demo devices for testing."""
    from app.infrastructure.database.models import Device, DeviceMonitoringState
    
    devices = []
    for i in range(3):
        device = Device(
            device_id=f"device-{i}",
            hostname=f"host{i}.example.com",
            ip_address=f"192.168.1.{100 + i}",
            device_type="router",
            site="us-east-1",
            tenant_id=demo_user.tenant_id,
        )
        
        # Add monitoring state
        state = DeviceMonitoringState(
            device_id=device.id,
            monitoring_state="HEALTHY" if i == 0 else "DRIFTING",
            current_score=90 - (i * 20),
            consecutive_failures=i,
            active_drift_count=i if i > 0 else 0,
            poll_interval=300,
        )
        
        test_db_session.add(device)
        test_db_session.add(state)
        devices.append(device)
    
    await test_db_session.commit()
    return devices


# Pytest markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests",
    )
    config.addinivalue_line(
        "markers",
        "security: marks tests as security-related tests",
    )


# Test execution options
def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    for item in items:
        # All coroutine tests get the asyncio marker.
        if item.get_closest_marker("asyncio") is None and inspect.iscoroutinefunction(getattr(item, "obj", None)):
            item.add_marker(pytest.mark.asyncio)
