"""Unit tests for provider abstractions."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.providers.llm.interface import ILlmProvider
from app.providers.card.interface import ICardProvider, ExternalMerchantDTO


# ============================================================================
# LLM Provider Tests
# ============================================================================


@pytest.mark.asyncio
async def test_llm_provider_generate(mock_llm_provider):
    """Test LLM provider generate method."""
    result = await mock_llm_provider.generate("Test prompt")
    assert result == "Test generated text"
    mock_llm_provider.generate.assert_called_once_with("Test prompt")


@pytest.mark.asyncio
async def test_llm_provider_embed(mock_llm_provider):
    """Test LLM provider embed method returns correct dimensions."""
    embedding = await mock_llm_provider.embed("Test text")
    assert len(embedding) == 1536
    assert all(isinstance(v, (int, float)) for v in embedding)


@pytest.mark.asyncio
async def test_llm_provider_research(mock_llm_provider):
    """Test LLM provider research method."""
    result = await mock_llm_provider.research("What is a coffee shop?")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_llm_provider_name(mock_llm_provider):
    """Test LLM provider name property."""
    assert mock_llm_provider.provider_name == "openai"


@pytest.mark.asyncio
async def test_llm_provider_multiple_calls(mock_llm_provider):
    """Test LLM provider handles multiple calls correctly."""
    embed1 = await mock_llm_provider.embed("text1")
    embed2 = await mock_llm_provider.embed("text2")

    assert len(embed1) == 1536
    assert len(embed2) == 1536
    assert mock_llm_provider.embed.call_count == 2


# ============================================================================
# Card Provider Tests
# ============================================================================


@pytest.mark.asyncio
async def test_card_provider_normalize_merchant(mock_card_provider):
    """Test card provider normalize_merchant method."""
    raw_data = {"id": "test_id", "name": "Test Merchant"}
    result = await mock_card_provider.normalize_merchant(raw_data)

    assert isinstance(result, ExternalMerchantDTO)
    assert result.name == "TEST MERCHANT"
    assert result.provider == "pomelo"
    assert result.provider_id == "ext_123"


@pytest.mark.asyncio
async def test_card_provider_get_transactions(mock_card_provider):
    """Test card provider get_transactions method."""
    result = await mock_card_provider.get_transactions()
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_card_provider_lookup_merchant(mock_card_provider):
    """Test card provider lookup_merchant method."""
    result = await mock_card_provider.lookup_merchant("Test Merchant")
    assert isinstance(result, dict)
    assert "id" in result


@pytest.mark.asyncio
async def test_card_provider_name(mock_card_provider):
    """Test card provider name property."""
    assert mock_card_provider.provider_name == "pomelo"


@pytest.mark.asyncio
async def test_external_merchant_dto_creation():
    """Test ExternalMerchantDTO creation and attributes."""
    dto = ExternalMerchantDTO(
        name="Test Merchant",
        provider="pomelo",
        provider_id="ext_123",
        mcc_code="5411",
        category="grocery",
        raw_data={"id": "ext_123"}
    )

    assert dto.name == "Test Merchant"
    assert dto.provider == "pomelo"
    assert dto.provider_id == "ext_123"
    assert dto.mcc_code == "5411"
    assert dto.category == "grocery"


@pytest.mark.asyncio
async def test_external_merchant_dto_optional_fields():
    """Test ExternalMerchantDTO with optional fields."""
    dto = ExternalMerchantDTO(
        name="Test Merchant",
        provider="pomelo",
        provider_id="ext_123"
    )

    assert dto.mcc_code is None
    assert dto.category is None
    assert dto.raw_data is None


# ============================================================================
# Embedding Provider Tests
# ============================================================================


@pytest.mark.asyncio
async def test_embedding_provider_store(mock_embedding_provider):
    """Test embedding provider store method."""
    from uuid import uuid4
    embedding = [0.1] * 1536
    result = await mock_embedding_provider.store_embedding(embedding)
    assert result is not None


@pytest.mark.asyncio
async def test_embedding_provider_search(mock_embedding_provider):
    """Test embedding provider search method."""
    embedding = [0.1] * 1536
    results = await mock_embedding_provider.search_embeddings(embedding)
    assert isinstance(results, list)


# ============================================================================
# Provider Interface Tests
# ============================================================================


def test_llm_provider_is_abstract():
    """Test that ILlmProvider is abstract."""
    from abc import ABC
    assert issubclass(ILlmProvider, ABC)


def test_card_provider_is_abstract():
    """Test that ICardProvider is abstract."""
    from abc import ABC
    assert issubclass(ICardProvider, ABC)


@pytest.mark.asyncio
async def test_mock_llm_provider_consistency(mock_llm_provider):
    """Test that mock LLM provider behaves consistently."""
    embed1 = await mock_llm_provider.embed("same text")
    embed2 = await mock_llm_provider.embed("same text")

    # Both should return same structure
    assert len(embed1) == len(embed2)


@pytest.mark.asyncio
async def test_mock_card_provider_consistency(mock_card_provider):
    """Test that mock card provider behaves consistently."""
    raw_data = {"id": "test", "name": "Test"}

    dto1 = await mock_card_provider.normalize_merchant(raw_data)
    dto2 = await mock_card_provider.normalize_merchant(raw_data)

    # Both should return same structure
    assert dto1.name == dto2.name
    assert dto1.provider == dto2.provider
