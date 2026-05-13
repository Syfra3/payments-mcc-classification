"""Pomelo card provider implementation."""

from typing import Optional, Dict, Any, List
import httpx
import structlog

from app.providers.card.interface import ICardProvider, ExternalMerchantDTO
from app.core.exceptions import IntegrationError

logger = structlog.get_logger(__name__)


class PomeloProvider(ICardProvider):
    """Pomelo payment processor provider."""

    def __init__(self, api_key: str, base_url: str = "https://api.pomelo.dev"):
        """Initialize Pomelo provider."""
        if not api_key:
            raise ValueError("Pomelo API key is required")

        self._api_key = api_key
        self._base_url = base_url
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "pomelo"

    async def normalize_merchant(self, raw_data: Dict[str, Any]) -> ExternalMerchantDTO:
        """Normalize Pomelo merchant data."""
        return ExternalMerchantDTO(
            name=(raw_data.get("name") or raw_data.get("merchant_name", "")).upper(),
            provider="pomelo",
            provider_id=raw_data.get("merchant_id") or raw_data.get("id", ""),
            mcc_code=raw_data.get("mcc"),
            logo_url=raw_data.get("logo_url"),
            category=raw_data.get("category"),
            raw_data=raw_data,
        )

    async def get_transactions(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get transactions from Pomelo."""
        filters = filters or {}
        page_size = filters.get("page_size", 100)
        all_transactions: List[Dict[str, Any]] = []

        try:
            page = 0
            while True:
                params = {**filters, "page": page, "page_size": page_size}
                response = await self._client.get("/transactions", params=params)
                response.raise_for_status()

                data = response.json()
                items = data.get("data", [])

                if not items:
                    break

                all_transactions.extend(items)
                page += 1

                # Stop if we've reached the total count
                total = data.get("total", 0)
                if len(all_transactions) >= total:
                    break

            logger.info(f"Retrieved {len(all_transactions)} transactions from Pomelo")
            return all_transactions

        except httpx.HTTPStatusError as e:
            error_msg = f"Pomelo API error: {e.response.status_code}"
            logger.error(error_msg, status=e.response.status_code)
            raise IntegrationError(error_msg) from e
        except httpx.TimeoutException as e:
            error_msg = "Pomelo API timeout"
            logger.error(error_msg)
            raise IntegrationError(error_msg) from e
        except httpx.HTTPError as e:
            error_msg = f"Pomelo API error: {e}"
            logger.error(error_msg, error=str(e))
            raise IntegrationError(error_msg) from e

    async def lookup_merchant(self, name: str) -> Optional[Dict[str, Any]]:
        """Look up merchant by name on Pomelo."""
        try:
            response = await self._client.get(
                "/merchants/search",
                params={"q": name},
            )
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            if results:
                logger.info(f"Found Pomelo merchant: {name}")
                return results[0]

            logger.debug(f"No Pomelo merchant found: {name}")
            return None

        except httpx.HTTPError as e:
            error_msg = f"Pomelo lookup error: {e}"
            logger.warning(error_msg, error=str(e))
            # Return None on error, don't raise (non-blocking operation)
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def __del__(self):
        """Clean up resources."""
        try:
            if hasattr(self, "_client"):
                import asyncio

                try:
                    asyncio.run(self._client.aclose())
                except RuntimeError:
                    pass
        except Exception:
            pass
