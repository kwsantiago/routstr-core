import asyncio
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock, AsyncMock

# Save original environment variables
ORIGINAL_ENV = os.environ.copy()

# Set test environment variables before importing the app
TEST_ENV = {
    "UPSTREAM_BASE_URL": "https://api.example.com",
    "UPSTREAM_API_KEY": "test-upstream-key",
    "NAME": "TestRoutstrNode",
    "DESCRIPTION": "Test Node",
    "NPUB": "npub1test",
    "MINT": "https://test.mint.com",
    "HTTP_URL": "http://test.example.com",
    "ONION_URL": "http://test.onion",
    "CORS_ORIGINS": "*",
    "RECEIVE_LN_ADDRESS": "test@lightning.address",
    "COST_PER_REQUEST": "1",
    "COST_PER_1K_INPUT_TOKENS": "0",
    "COST_PER_1K_OUTPUT_TOKENS": "0",
    "MODEL_BASED_PRICING": "false"
}

# Apply test environment
os.environ.update(TEST_ENV)

# Mock the cashu wallet initialization before importing
with patch("router.cashu._initialize_wallet") as mock_init_wallet:
    mock_wallet = AsyncMock()
    mock_wallet.available_balance = 1000
    mock_wallet.proofs = []
    mock_wallet.split = AsyncMock(return_value=([], []))
    mock_init_wallet.return_value = mock_wallet
    
    with patch("router.cashu.WALLET", mock_wallet):
        from router.main import app
        from router.db import get_session
        from router.models import MODELS


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test database engine - new for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncSession:
    """Create a test database session."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
def test_client() -> TestClient:
    """Create a test client for the FastAPI app."""
    with patch.dict(os.environ, TEST_ENV, clear=True):
        with patch("router.cashu._initialize_wallet") as mock_init:
            mock_wallet = AsyncMock()
            mock_wallet.available_balance = 1000
            mock_wallet.proofs = []
            mock_wallet.split = AsyncMock(return_value=([], []))
            mock_init.return_value = mock_wallet
            
            with patch("router.models.update_sats_pricing") as mock_update:
                mock_update.return_value = None
                yield TestClient(app)


@pytest_asyncio.fixture
async def async_client(test_session) -> AsyncClient:
    """Create an async test client with dependency overrides."""
    async def override_get_session():
        yield test_session
    
    app.dependency_overrides[get_session] = override_get_session
    
    # Mock startup tasks
    with patch.dict(os.environ, TEST_ENV, clear=True):
        with patch("router.cashu._initialize_wallet") as mock_init:
            mock_wallet = AsyncMock()
            mock_wallet.available_balance = 1000
            mock_wallet.proofs = []
            mock_wallet.split = AsyncMock(return_value=([], []))
            mock_init.return_value = mock_wallet
            
            with patch("router.models.update_sats_pricing") as mock_update:
                mock_update.return_value = None
                
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test"
                ) as client:
                    yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def mock_models():
    """Mock models data for testing."""
    return [
        {
            "id": "gpt-4",
            "name": "GPT-4",
            "created": 1680000000,
            "description": "Test model",
            "context_length": 8192,
            "architecture": {
                "modality": "text",
                "input_modalities": ["text"],
                "output_modalities": ["text"],
                "tokenizer": "cl100k_base",
                "instruct_type": "none"
            },
            "pricing": {
                "prompt": 0.03,
                "completion": 0.06,
                "request": 0.001,
                "image": 0.0,
                "web_search": 0.0,
                "internal_reasoning": 0.0
            },
            "top_provider": {
                "context_length": 8192,
                "max_completion_tokens": 4096,
                "is_moderated": False
            }
        }
    ]


# Cleanup after all tests
@pytest.fixture(scope="session", autouse=True)
def cleanup():
    yield
    # Restore original environment carefully
    current_keys = set(os.environ.keys())
    original_keys = set(ORIGINAL_ENV.keys())
    
    # Remove keys that weren't in original
    for key in current_keys - original_keys:
        if key != 'PYTEST_CURRENT_TEST':  # Don't touch pytest's own variables
            os.environ.pop(key, None)
    
    # Restore original values
    for key, value in ORIGINAL_ENV.items():
        os.environ[key] = value 