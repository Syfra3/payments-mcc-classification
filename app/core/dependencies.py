"""FastAPI dependency injection for providers and session."""

from functools import lru_cache
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.context import get_session
from app.providers.llm import ILlmProvider, OpenAiProvider
from app.providers.card import ICardProvider, PomeloProvider
from app.providers.google_places import GooglePlacesProvider
from app.providers.s3 import S3Provider
from app.providers.sns import SnsPublisher
import structlog

logger = structlog.get_logger(__name__)

# Singleton instances
_llm_provider: Optional[ILlmProvider] = None
_card_provider: Optional[ICardProvider] = None
_google_places_provider: Optional[GooglePlacesProvider] = None
_s3_provider: Optional[S3Provider] = None
_sns_publisher: Optional[SnsPublisher] = None


def get_llm_provider() -> ILlmProvider:
    """Get LLM provider (singleton)."""
    global _llm_provider

    if _llm_provider is None:
        logger.info("Initializing LLM provider")
        _llm_provider = OpenAiProvider(
            api_key=settings.openai_api_key,
            embedding_model=settings.openai_embedding_model,
        )

    return _llm_provider


def get_card_provider() -> ICardProvider:
    """Get card provider (singleton)."""
    global _card_provider

    if _card_provider is None:
        logger.info("Initializing card provider")
        _card_provider = PomeloProvider(
            api_key=settings.pomelo_api_key,
            base_url=settings.pomelo_base_url,
        )

    return _card_provider


def get_google_places_provider() -> Optional[GooglePlacesProvider]:
    """Get Google Places provider (singleton, optional)."""
    global _google_places_provider

    if _google_places_provider is not None:
        return _google_places_provider

    try:
        from app.core.config import settings

        if not hasattr(settings, "google_places_api_key") or not settings.google_places_api_key:
            logger.debug("Google Places API key not configured")
            return None

        logger.info("Initializing Google Places provider")
        _google_places_provider = GooglePlacesProvider(
            api_key=settings.google_places_api_key
        )
        return _google_places_provider

    except Exception as e:
        logger.warning(f"Failed to initialize Google Places provider: {e}")
        return None


def get_s3_provider() -> Optional[S3Provider]:
    """Get S3 provider (singleton, optional)."""
    global _s3_provider

    if _s3_provider is not None:
        return _s3_provider

    try:
        from app.core.config import settings

        # Check if S3 credentials are configured
        if not (
            hasattr(settings, "aws_access_key")
            and settings.aws_access_key
            and hasattr(settings, "aws_secret_key")
            and settings.aws_secret_key
            and hasattr(settings, "s3_bucket")
            and settings.s3_bucket
        ):
            logger.debug("S3 credentials not configured")
            return None

        logger.info("Initializing S3 provider")
        _s3_provider = S3Provider(
            access_key=settings.aws_access_key,
            secret_key=settings.aws_secret_key,
            bucket=settings.s3_bucket,
        )
        return _s3_provider

    except Exception as e:
        logger.warning(f"Failed to initialize S3 provider: {e}")
        return None


def get_sns_publisher() -> Optional[SnsPublisher]:
    """Get SNS publisher (singleton, optional)."""
    global _sns_publisher

    if _sns_publisher is not None:
        return _sns_publisher

    try:
        from app.core.config import settings

        if not (hasattr(settings, "sns_topic_arn") and settings.sns_topic_arn):
            logger.debug("SNS topic ARN not configured")
            return None

        logger.info("Initializing SNS publisher")
        _sns_publisher = SnsPublisher(topic_arn=settings.sns_topic_arn)
        return _sns_publisher

    except Exception as e:
        logger.warning(f"Failed to initialize SNS publisher: {e}")
        return None


async def get_session() -> AsyncSession:
    """Get the ambient database session from context."""
    from app.core.context import get_session as get_context_session

    session = get_context_session()
    if session is None:
        raise RuntimeError("No database session available in context")
    return session


def get_db_session() -> AsyncSession:
    """Get database session for dependency injection."""
    return get_session()


# Service dependencies

def get_merchant_service():
    """Get merchant service."""
    from app.services.merchant_service import MerchantService
    return MerchantService(llm_provider=get_llm_provider())


def get_mcc_service():
    """Get MCC service."""
    from app.services.mcc_service import MccService
    return MccService(llm_provider=get_llm_provider())


def get_external_merchant_service():
    """Get external merchant service."""
    from app.services.external_merchant_service import ExternalMerchantService
    return ExternalMerchantService(card_provider=get_card_provider())


def get_pipeline_engine():
    """Get pipeline engine."""
    from app.pipeline.engine import PipelineEngine
    return PipelineEngine()
