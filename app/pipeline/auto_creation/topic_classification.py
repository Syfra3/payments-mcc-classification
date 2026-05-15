"""Topic classification step using pluggable classifiers."""

from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.decorators import step
from app.services.classifiers.factory import get_classifier_factory
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)


@step(
    registry="AUTO_CREATION",
    order=5,
    execution_type="blocking",
    timeout_seconds=20,
    description="Classify merchant topic via pluggable classifier",
)
class TopicClassificationStep(BaseStep):
    """Step 5: Classify merchant's topic/category using pluggable classifier.

    Supports LLM, rule-based, and lookup table strategies.
    Tenant context flows via PipelineContext dict.
    """

    def __init__(self):
        """Initialize step with classifier factory."""
        super().__init__()
        self._factory = get_classifier_factory()

    def should_run(self, context: PipelineContext) -> bool:
        """Only run if merchant not already found and merchant name provided."""
        merchant_exists = context.get("merchant") is not None
        classification_result = context.get("classification_result")
        merchant_name = context.get("name")
        return not merchant_exists and not classification_result and merchant_name is not None

    async def execute(self, context: PipelineContext) -> dict:
        """
        Classify merchant using configured classifier strategy.

        Args:
            context: Pipeline context with 'name', optional 'description', and tenant_id

        Returns:
            Dict with classification_result and mcc_codes
        """
        merchant_name = context.get("name")
        description = context.get("description", merchant_name)
        tenant_id = context.get("tenant_id", settings.default_tenant)

        if not merchant_name:
            logger.warning("No merchant name provided for classification")
            return {
                "mcc_classified": False,
                "error": "no_name",
                "mcc_codes": [],
            }

        try:
            # Get the configured classifier
            classifier = await self._factory.get_classifier()

            # Classify the merchant
            result = await classifier.classify(merchant_name, tenant_id, description)

            # Store result in context
            context.set("classification_result", result)

            # For backward compatibility, also extract MCC codes if available
            # (This will be extended in Phase 2 when we implement MCC result mapping)
            mcc_codes = context.get("mcc_codes", [])

            self._logger.info(
                "Topic classification successful",
                merchant_name=merchant_name,
                category=result.category,
                confidence=result.confidence,
                classifier_type=result.classifier_type,
                tenant_id=tenant_id,
            )

            return {
                "mcc_classified": True,
                "category": result.category,
                "confidence": result.confidence,
                "classifier_type": result.classifier_type,
                "mcc_codes": mcc_codes,
            }

        except Exception as e:
            self._logger.error(
                "Topic classification failed",
                merchant_name=merchant_name,
                tenant_id=tenant_id,
                error=str(e),
            )
            return {
                "mcc_classified": False,
                "error": str(e),
                "mcc_codes": [],
            }


# Backward compatibility alias
MccClassificationStep = TopicClassificationStep
