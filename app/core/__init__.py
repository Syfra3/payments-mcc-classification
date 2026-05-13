"""Core application infrastructure."""

from app.core.config import settings
from app.core.context import get_session, set_session, reset_session, transactional
from app.core.exceptions import (
    AppException,
    ResourceNotFound,
    ValidationFailed,
    AuthenticationFailed,
    AuthorizationFailed,
    ConflictError,
    IntegrationError,
    DuplicateError,
)
from app.core.auth import verify_hmac_signature, verify_request_signature, require_hmac_auth
from app.core.database import engine, async_session_local, get_db_session, init_db, dispose_db

__all__ = [
    "settings",
    "get_session",
    "set_session",
    "reset_session",
    "transactional",
    "AppException",
    "ResourceNotFound",
    "ValidationFailed",
    "AuthenticationFailed",
    "AuthorizationFailed",
    "ConflictError",
    "IntegrationError",
    "DuplicateError",
    "verify_hmac_signature",
    "verify_request_signature",
    "require_hmac_auth",
    "engine",
    "async_session_local",
    "get_db_session",
    "init_db",
    "dispose_db",
]
