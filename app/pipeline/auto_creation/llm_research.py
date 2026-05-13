"""LLM-based merchant research step."""

from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.decorators import step
from app.providers.llm.interface import ILlmProvider
from app.core.dependencies import get_llm_provider


@step(
    registry="AUTO_CREATION",
    order=2,
    execution_type="blocking",
    timeout_seconds=30,
    description="Research merchant via LLM and web search",
)
class LlmResearchStep(BaseStep):
    """Step 2: Use LLM to research merchant via Tavily web search."""

    def __init__(self):
        """Initialize step with LLM provider."""
        super().__init__()
        try:
            self._llm = get_llm_provider()
        except Exception:
            self._llm = None

    def should_run(self, context: PipelineContext) -> bool:
        """Only run if merchant not already found and LLM is available."""
        merchant_exists = context.get("merchant") is not None
        return not merchant_exists and self._llm is not None

    async def execute(self, context: PipelineContext) -> dict:
        """
        Research merchant using LLM and Tavily web search.

        Args:
            context: Pipeline context with 'name' field

        Returns:
            Dict with research results
        """
        if not self._llm:
            self._logger.warning("LLM provider not available")
            return {"research_result": None, "error": "llm_unavailable"}

        merchant_name = context.get("name")
        if not merchant_name:
            return {"research_result": None, "error": "no_name"}

        try:
            research_result = await self._llm.research(merchant_name, max_results=5)
            context.set("research_result", research_result)
            self._logger.info(
                "Merchant research completed",
                merchant_name=merchant_name,
                result_length=len(research_result) if research_result else 0,
            )
            return {"research_result": research_result}
        except Exception as e:
            self._logger.error(
                "Merchant research failed",
                merchant_name=merchant_name,
                error=str(e),
            )
            return {"research_result": None, "error": str(e)}
