"""Shared pytest fixtures for all tests."""
import asyncio
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.context import get_session, reset_session, set_session
from app.models import Base


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def test_engine():
    """Create an in-memory SQLite test database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test session with automatic cleanup."""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        token = set_session(session)
        yield session
        reset_session(token)
        # Rollback to cleanup
        await session.rollback()


@pytest_asyncio.fixture
async def session_factory(test_engine):
    """Return a sessionmaker for creating multiple sessions."""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return async_session


# ============================================================================
# Provider Mocks
# ============================================================================


@pytest.fixture
def mock_llm_provider():
    """Mock ILlmProvider for testing."""
    provider = AsyncMock()
    provider.provider_name = "openai"

    # Mock generate response
    mock_response = MagicMock()
    mock_response.text = '{"name": "TEST MERCHANT", "category": "retail"}'
    mock_response.model = "gpt-4"
    mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 20}
    provider.generate = AsyncMock(return_value="Test generated text")

    # Mock embed response - return a list of floats
    provider.embed = AsyncMock(return_value=[0.1] * 1536)

    # Mock research response
    provider.research = AsyncMock(return_value="Mock research result about test merchant")

    return provider


@pytest.fixture
def mock_card_provider():
    """Mock ICardProvider for testing."""
    from app.providers.card.interface import ExternalMerchantDTO

    provider = AsyncMock()
    provider.provider_name = "pomelo"

    # Mock normalize_merchant response
    mock_dto = ExternalMerchantDTO(
        provider="pomelo",
        provider_id="ext_123",
        name="TEST MERCHANT",
        mcc_code="5411",
        raw_data={"id": "ext_123", "name": "Test Merchant"}
    )
    provider.normalize_merchant = AsyncMock(return_value=mock_dto)

    # Mock other methods
    provider.get_transactions = AsyncMock(return_value=[])
    provider.lookup_merchant = AsyncMock(return_value={"id": "ext_123", "name": "Test Merchant"})

    return provider


@pytest.fixture
def mock_embedding_provider():
    """Mock embedding provider for testing."""
    provider = AsyncMock()
    provider.store_embedding = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
    provider.search_embeddings = AsyncMock(return_value=[])
    return provider


# ============================================================================
# Context Fixtures
# ============================================================================


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Factory Fixtures
# ============================================================================


@pytest.fixture
def sample_merchant_data():
    """Sample merchant data for tests."""
    return {
        "name": "Whole Foods Market",
        "provider": "pomelo",
        "external_id": f"ext_{uuid.uuid4()}",
        "embedding": None,
        "logo_url": None,
        "weight": 1.0,
        "metadata": {"human_created": False},
    }


@pytest.fixture
def sample_mcc_data():
    """Sample MCC data for tests."""
    return {
        "code": "5411",
        "description": "Grocery stores and supermarkets",
        "category_id": None,
        "embedding": None,
    }


@pytest.fixture
def sample_external_merchant_data():
    """Sample external merchant data for tests."""
    return {
        "provider": "pomelo",
        "provider_id": f"pomelo_{uuid.uuid4()}",
        "name": "External Merchant",
        "raw_data": {"id": f"pomelo_{uuid.uuid4()}", "name": "External Merchant"},
    }
