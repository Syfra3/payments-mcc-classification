"""Generate embedding for merchant step."""

from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.decorators import step
from app.providers.llm.interface import ILlmProvider
from app.core.dependencies import get_llm_provider


@step(
    registry="AUTO_CREATION",
    order=3,
    execution_type="blocking",
    timeout_seconds=15,
    description="Generate embedding for merchant name",
)
class GenerateEmbeddingStep(BaseStep):
    """Step 3: Generate embedding vector for merchant name."""

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
        embedding_exists = context.get("embedding") is not None
        return not merchant_exists and not embedding_exists and self._llm is not None

    async def execute(self, context: PipelineContext) -> dict:
        """
        Generate embedding for merchant name.

        Args:
            context: Pipeline context with 'name' field

        Returns:
            Dict with embedding vector
        """
        if not self._llm:
            self._logger.warning("LLM provider not available for embedding")
            return {"embedding_generated": False, "error": "llm_unavailable"}

        merchant_name = context.get("name")
        if not merchant_name:
            return {"embedding_generated": False, "error": "no_name"}

        try:
            embedding_vec = await self._llm.embed(merchant_name)
            context.set("embedding", embedding_vec)
            self._logger.info(
                "Embedding generated",
                merchant_name=merchant_name,
                embedding_dim=len(embedding_vec) if embedding_vec else 0,
            )
            return {"embedding_generated": True, "embedding_dim": len(embedding_vec)}
        except Exception as e:
            self._logger.error(
                "Embedding generation failed",
                merchant_name=merchant_name,
                error=str(e),
            )
            return {"embedding_generated": False, "error": str(e)}
