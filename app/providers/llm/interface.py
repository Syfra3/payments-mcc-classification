"""Abstract interface for LLM providers."""

from abc import ABC, abstractmethod
from typing import Optional


class ILlmProvider(ABC):
    """Abstract interface for Language Model providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """
        Generate text from a prompt.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Temperature for sampling (0-2)
            **kwargs: Additional provider-specific arguments

        Returns:
            Generated text
        """
        raise NotImplementedError

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """
        Generate embeddings for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        raise NotImplementedError

    @abstractmethod
    async def research(self, query: str, max_results: int = 5) -> str:
        """
        Research a query using web search (Tavily).

        Args:
            query: Research query
            max_results: Maximum number of results

        Returns:
            Formatted research results as string
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the model name."""
        raise NotImplementedError
