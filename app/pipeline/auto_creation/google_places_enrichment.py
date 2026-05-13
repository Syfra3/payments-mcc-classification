"""Google Places enrichment step (non-blocking)."""

from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.decorators import step
from app.core.dependencies import get_google_places_provider


@step(
    registry="AUTO_CREATION",
    order=4,
    execution_type="non_blocking",
    timeout_seconds=10,
    description="Optional: enrich with Google Places data",
)
class GooglePlacesEnrichmentStep(BaseStep):
    """Step 4: Optional enrichment with Google Places data (non-blocking)."""

    def __init__(self):
        """Initialize step with Google Places provider."""
        super().__init__()
        try:
            self._google_places = get_google_places_provider()
        except Exception:
            self._google_places = None

    def should_run(self, context: PipelineContext) -> bool:
        """Only run if Google Places is available."""
        return self._google_places is not None

    async def execute(self, context: PipelineContext) -> dict:
        """
        Enrich merchant data with Google Places information.

        Args:
            context: Pipeline context with 'name' field

        Returns:
            Dict with enrichment result
        """
        if not self._google_places:
            self._logger.debug("Google Places provider not available")
            return {"google_place_enriched": False, "reason": "provider_unavailable"}

        merchant_name = context.get("name")
        if not merchant_name:
            return {"google_place_enriched": False, "reason": "no_name"}

        try:
            place_data = await self._google_places.lookup(merchant_name)
            if place_data:
                context.set("location_metadata", place_data)
                self._logger.info(
                    "Google Places enrichment successful",
                    merchant_name=merchant_name,
                    place_id=place_data.get("place_id"),
                )
                return {"google_place_enriched": True, "place": place_data}
            else:
                self._logger.info(
                    "No Google Place found",
                    merchant_name=merchant_name,
                )
                return {"google_place_enriched": False, "reason": "not_found"}
        except Exception as e:
            # Non-blocking: log but don't fail
            self._logger.warning(
                "Google Places enrichment failed",
                merchant_name=merchant_name,
                error=str(e),
            )
            return {"google_place_enriched": False, "error": str(e)}
