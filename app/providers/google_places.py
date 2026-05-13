"""Google Places API provider (optional, non-blocking)."""

from typing import Optional, Dict, Any
import httpx
import structlog

logger = structlog.get_logger(__name__)


class GooglePlacesProvider:
    """Google Places API client for merchant lookup."""

    def __init__(self, api_key: str):
        """Initialize Google Places provider."""
        if not api_key:
            raise ValueError("Google Places API key is required")

        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0)

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "google_places"

    async def lookup(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Look up a place by query.

        Args:
            query: Place name or address to search

        Returns:
            Place data dict with name, lat, lng, address, rating, review_count
            or None if not found
        """
        try:
            # Use Find Place from Text API
            response = await self._client.get(
                "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
                params={
                    "input": query,
                    "key": self._api_key,
                    "fields": "formatted_address,geometry,name,rating,user_ratings_total,types",
                },
            )

            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK" or not data.get("candidates"):
                logger.debug(f"No places found for query: {query}")
                return None

            candidate = data["candidates"][0]

            result = {
                "name": candidate.get("name"),
                "address": candidate.get("formatted_address"),
                "rating": candidate.get("rating"),
                "review_count": candidate.get("user_ratings_total"),
            }

            geometry = candidate.get("geometry", {})
            location = geometry.get("location", {})
            result["lat"] = location.get("lat")
            result["lng"] = location.get("lng")

            logger.info(f"Found place via Google Places: {result.get('name')}")
            return result

        except httpx.HTTPError as e:
            # Non-blocking error - log and return None
            logger.warning(f"Google Places lookup error: {e}", error=str(e))
            return None
        except Exception as e:
            # Non-blocking error - log and return None
            logger.warning(f"Unexpected error in Google Places lookup: {e}", error=str(e))
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
