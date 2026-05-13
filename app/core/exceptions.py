"""Custom exception classes and error handling."""

from typing import Any, Dict, Optional


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the exception."""
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

    def to_response(self) -> Dict[str, Any]:
        """Convert exception to response dict."""
        response = {"error": self.error_code, "message": self.message}
        if self.details:
            response["details"] = self.details
        return response


class ResourceNotFound(AppException):
    """Resource not found error (404)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=404,
            error_code="RESOURCE_NOT_FOUND",
            details=details,
        )


class ValidationFailed(AppException):
    """Validation error (422)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_FAILED",
            details=details,
        )


class AuthenticationFailed(AppException):
    """Authentication error (401)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_FAILED",
            details=details,
        )


class AuthorizationFailed(AppException):
    """Authorization error (403)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_FAILED",
            details=details,
        )


class ConflictError(AppException):
    """Conflict error (409)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT",
            details=details,
        )


class IntegrationError(AppException):
    """External service integration error (503)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=503,
            error_code="INTEGRATION_ERROR",
            details=details,
        )


class DuplicateError(AppException):
    """Duplicate resource error (409)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=409,
            error_code="DUPLICATE_RESOURCE",
            details=details,
        )
