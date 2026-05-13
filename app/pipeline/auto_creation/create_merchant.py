"""Create merchant step."""

from uuid import UUID
from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.decorators import step
from app.models.merchant import Merchant
from app.repositories.merchant_repository import MerchantRepository
from app.repositories.mcc_repository import MccRepository
from app.repositories.outbox_repository import OutboxRepository
from app.providers.embedding import store_embedding


@step(
    registry="AUTO_CREATION",
    order=6,
    execution_type="blocking",
    timeout_seconds=15,
    description="Create merchant record with all data",
)
class CreateMerchantStep(BaseStep):
    """Step 6: Create the Merchant record with all collected data."""

    def __init__(self):
        """Initialize step with repositories."""
        super().__init__()
        self._merchant_repo = MerchantRepository()
        self._mcc_repo = MccRepository()
        self._outbox_repo = OutboxRepository()

    def should_run(self, context: PipelineContext) -> bool:
        """Only run if merchant doesn't already exist."""
        return context.get("merchant") is None

    async def execute(self, context: PipelineContext) -> dict:
        """
        Create merchant record from context data.

        Args:
            context: Pipeline context with merchant data

        Returns:
            Dict with merchant_id and creation status
        """
        merchant_name = context.get("name")
        provider = context.get("provider", "auto_created")
        logo_url = context.get("logo_url")
        embedding_vec = context.get("embedding")
        mcc_codes = context.get("mcc_codes", [])

        if not merchant_name:
            return {
                "created": False,
                "error": "missing_required_field",
                "field": "name",
            }

        try:
            # Create merchant
            merchant = Merchant(
                name=merchant_name,
                provider=provider,
                logo_url=logo_url,
                metadata={
                    "human_created": False,
                    "source": "auto_creation_pipeline",
                },
            )
            merchant = await self._merchant_repo.create(merchant)

            # Assign MCCs
            for mcc_code in mcc_codes:
                mcc = await self._mcc_repo.get_by_code(mcc_code)
                if mcc:
                    await self._mcc_repo.add_merchant_to_mcc(mcc.id, merchant.id)

            # Store embedding if available
            if embedding_vec:
                try:
                    await store_embedding("merchant", merchant.id, embedding_vec)
                except Exception as e:
                    self._logger.warning(
                        "Failed to store embedding",
                        merchant_id=str(merchant.id),
                        error=str(e),
                    )

            # Update context
            context.set("merchant", merchant)
            context.set("merchant_id", merchant.id)

            # Create outbox event for downstream notification
            await self._outbox_repo.create_event(
                event_type="merchant.created",
                aggregate_id=merchant.id,
                aggregate_type="Merchant",
                payload={
                    "merchant_id": str(merchant.id),
                    "name": merchant.name,
                    "provider": merchant.provider,
                    "mcc_codes": mcc_codes,
                },
            )

            self._logger.info(
                "Merchant created successfully",
                merchant_id=str(merchant.id),
                merchant_name=merchant.name,
                mcc_count=len(mcc_codes),
            )

            return {
                "created": True,
                "merchant_id": str(merchant.id),
                "merchant_name": merchant.name,
                "mcc_count": len(mcc_codes),
            }
        except Exception as e:
            self._logger.error(
                "Merchant creation failed",
                merchant_name=merchant_name,
                error=str(e),
            )
            return {
                "created": False,
                "error": str(e),
                "merchant_id": None,
            }
