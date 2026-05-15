"""Exception hierarchy for classification services."""

from typing import Optional


class ClassificationException(Exception):
    """Base exception for classification operations."""

    def __init__(self, message: str, tenant_id: Optional[str] = None):
        """Initialize exception with optional tenant context."""
        self.message = message
        self.tenant_id = tenant_id
        super().__init__(message)


class ClassificationError(ClassificationException):
    """Raised when classification fails due to invalid input or logic."""

    pass


class TenantNotFoundError(ClassificationException):
    """Raised when a tenant does not exist or has no configuration."""

    def __init__(self, tenant_id: str, message: Optional[str] = None):
        """Initialize with tenant_id."""
        msg = message or f"Tenant '{tenant_id}' not found or not configured"
        super().__init__(msg, tenant_id)


class InvalidClassifierTypeError(ClassificationException):
    """Raised when an unsupported classifier type is requested."""

    def __init__(self, classifier_type: str):
        """Initialize with invalid classifier type."""
        msg = f"Invalid classifier type '{classifier_type}'. Supported: 'llm', 'rules', 'lookup'"
        super().__init__(msg)


class UnauthorizedTenantAccessError(ClassificationException):
    """Raised when attempting to access resources across tenant boundaries."""

    def __init__(self, tenant_id: str, resource_id: str, message: Optional[str] = None):
        """Initialize with tenant and resource context."""
        msg = message or f"Unauthorized access to resource '{resource_id}' for tenant '{tenant_id}'"
        super().__init__(msg, tenant_id)


class ClassificationServiceError(ClassificationException):
    """Raised when an external service (e.g., OpenAI) fails."""

    def __init__(self, service: str, original_error: str, message: Optional[str] = None):
        """Initialize with service and error details."""
        msg = message or f"Classification service error from '{service}': {original_error}"
        super().__init__(msg)


class ConfigurationError(ClassificationException):
    """Raised when configuration is invalid or incomplete."""

    def __init__(self, message: str):
        """Initialize with configuration error message."""
        super().__init__(message)


class RuleLoadError(ClassificationException):
    """Raised when rule files cannot be loaded or parsed."""

    def __init__(self, path: str, reason: str):
        """Initialize with file path and error reason."""
        msg = f"Failed to load rules from '{path}': {reason}"
        super().__init__(msg)
