"""Abstract interface for card payment providers."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from uuid import UUID


@dataclass
class ExternalMerchantDTO:
    """Normalized external merchant data."""

    name: str
    provider: str
    provider_id: str
    mcc_code: Optional[str] = None
    logo_url: Optional[str] = None
    category: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class ICardProvider(ABC):
    """Abstract interface for card payment providers."""

    @abstractmethod
    async def normalize_merchant(self, raw_data: Dict[str, Any]) -> ExternalMerchantDTO:
        """
        Normalize merchant data from provider format.

        Args:
            raw_data: Raw merchant data from provider

        Returns:
            Normalized ExternalMerchantDTO
        """
        raise NotImplementedError

    @abstractmethod
    async def get_transactions(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> list[Dict[str, Any]]:
        """
        Get transactions from the provider.

        Args:
            filters: Optional filters (page_size, offset, etc.)

        Returns:
            List of transaction dictionaries
        """
        raise NotImplementedError

    @abstractmethod
    async def lookup_merchant(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Look up merchant by name.

        Args:
            name: Merchant name to search

        Returns:
            Merchant data dict or None if not found
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name."""
        raise NotImplementedError
