"""Notify downstream services step (non-blocking)."""

from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.decorators import step
from app.core.dependencies import get_sns_publisher


@step(
    registry="AUTO_CREATION",
    order=7,
    execution_type="non_blocking",
    timeout_seconds=10,
    description="Publish notification to downstream services",
)
class NotifyDownstreamStep(BaseStep):
    """Step 7: Publish merchant creation notification to downstream services (non-blocking)."""

    def __init__(self):
        """Initialize step with SNS publisher."""
        super().__init__()
        try:
            self._sns = get_sns_publisher()
        except Exception:
            self._sns = None

    def should_run(self, context: PipelineContext) -> bool:
        """Only run if merchant was created."""
        return context.get("merchant") is not None and self._sns is not None

    async def execute(self, context: PipelineContext) -> dict:
        """
        Publish merchant creation notification via SNS.

        Args:
            context: Pipeline context with created merchant

        Returns:
            Dict with notification status
        """
        if not self._sns:
            self._logger.debug("SNS publisher not available")
            return {"notification_sent": False, "reason": "sns_unavailable"}

        merchant_id = context.get("merchant_id")
        merchant_name = context.get("name")
        mcc_codes = context.get("mcc_codes", [])

        if not merchant_id:
            return {"notification_sent": False, "reason": "no_merchant_id"}

        try:
            message = {
                "event_type": "merchant.created",
                "merchant_id": str(merchant_id),
                "merchant_name": merchant_name,
                "mcc_codes": mcc_codes,
            }
            await self._sns.publish(message, "merchant.created")

            self._logger.info(
                "Downstream notification sent",
                merchant_id=str(merchant_id),
                event_type="merchant.created",
            )
            return {"notification_sent": True, "merchant_id": str(merchant_id)}
        except Exception as e:
            # Non-blocking: log but don't fail
            self._logger.warning(
                "Downstream notification failed",
                merchant_id=str(merchant_id),
                error=str(e),
            )
            return {"notification_sent": False, "error": str(e)}
