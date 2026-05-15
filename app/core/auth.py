"""HMAC authentication and request verification."""

import hashlib
import hmac
from typing import Optional
from fastapi import Request, HTTPException, Depends
from app.core.config import settings


def verify_hmac_signature(message: str, signature: str, secret: str) -> bool:
    """
    Verify an HMAC-SHA256 signature.

    Args:
        message: The message that was signed
        signature: The signature to verify (hex string)
        secret: The shared secret

    Returns:
        True if signature is valid, False otherwise
    """
    # Compute expected signature
    expected_signature = hmac.new(
        secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()

    # Compare using constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature, expected_signature)


async def verify_request_signature(request: Request) -> None:
    """
    FastAPI dependency to verify request HMAC signature.

    Checks for X-API-Signature header and verifies it matches
    the request body signed with the HMAC secret.

    Raises:
        HTTPException: If signature is missing or invalid
    """
    # Get signature from header
    signature = request.headers.get("X-API-Signature")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-API-Signature header")

    # Get request body
    body = await request.body()
    message = body.decode("utf-8") if body else ""

    # Verify signature
    if not verify_hmac_signature(message, signature, settings.hmac_secret):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")


async def require_hmac_auth(request: Request) -> None:
    """
    FastAPI dependency for HMAC-protected endpoints.

    Usage:
        @app.post("/api/v1/merchants", dependencies=[Depends(require_hmac_auth)])
        async def create_merchant(data: MerchantCreate):
            ...
    """
    await verify_request_signature(request)
