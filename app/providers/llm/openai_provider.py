"""OpenAI LLM provider implementation."""

from typing import Optional
import httpx
import json
import structlog
from cachetools import LRUCache

from app.providers.llm.interface import ILlmProvider
from app.providers.llm.langfuse_client import create_trace

logger = structlog.get_logger(__name__)


class OpenAiProvider(ILlmProvider):
    """OpenAI provider implementation."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        embedding_model: str = "text-embedding-3-small",
    ):
        """Initialize OpenAI provider."""
        if not api_key:
            raise ValueError("OpenAI API key is required")

        self._api_key = api_key
        self._model = model
        self._embedding_model = embedding_model
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        self._embedding_cache: LRUCache[str, list[float]] = LRUCache(maxsize=1000)

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._model

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Generate text using OpenAI."""
        trace = create_trace("llm.generate", {"model": self._model, "prompt_length": len(prompt)})

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            span = trace.generation(name="chat_completion", input=messages) if trace else None

            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **kwargs,
                },
            )

            response.raise_for_status()
            data = response.json()
            result = data["choices"][0]["message"]["content"]

            if span:
                span.end(output=result)

            return result

        except httpx.HTTPError as e:
            error_msg = f"OpenAI API error: {e}"
            if trace and span:
                span.end(level="ERROR", status_message=error_msg)
            logger.error(error_msg, error=str(e))
            raise

    async def embed(self, text: str) -> list[float]:
        """Generate embeddings using OpenAI."""
        # Check cache first
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        trace = create_trace("llm.embed", {"model": self._embedding_model})

        try:
            span = trace.generation(name="embedding", input=text) if trace else None

            response = await self._client.post(
                "/embeddings",
                json={
                    "model": self._embedding_model,
                    "input": text,
                },
            )

            response.raise_for_status()
            data = response.json()
            embedding = data["data"][0]["embedding"]

            # Cache the result
            self._embedding_cache[text] = embedding

            if span:
                span.end(output={"dimensions": len(embedding)})

            return embedding

        except httpx.HTTPError as e:
            error_msg = f"OpenAI embedding error: {e}"
            if trace and span:
                span.end(level="ERROR", status_message=error_msg)
            logger.error(error_msg, error=str(e))
            raise

    async def research(self, query: str, max_results: int = 5) -> str:
        """Research using Tavily web search."""
        from app.core.config import settings

        if not settings.tavily_api_key:
            logger.warning("Tavily API key not configured, returning empty results")
            return ""

        trace = create_trace("llm.research", {"query": query, "max_results": max_results})

        try:
            span = trace.generation(name="tavily_search", input=query) if trace else None

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "query": query,
                        "api_key": settings.tavily_api_key,
                        "max_results": max_results,
                    },
                    timeout=30.0,
                )

                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])

                # Format results as markdown
                formatted = "\n\n".join(
                    f"**{r.get('title', 'Result')}**\n{r.get('content', '')}"
                    for r in results
                )

                if span:
                    span.end(output={"results_count": len(results)})

                return formatted

        except httpx.HTTPError as e:
            error_msg = f"Tavily search error: {e}"
            if trace and span:
                span.end(level="ERROR", status_message=error_msg)
            logger.error(error_msg, error=str(e))
            return ""  # Return empty string on error, don't raise

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def __del__(self):
        """Clean up resources."""
        try:
            # Try to close the client if it exists
            if hasattr(self, "_client"):
                import asyncio

                try:
                    asyncio.run(self._client.aclose())
                except RuntimeError:
                    # Event loop already closed, try without async
                    pass
        except Exception:
            pass
