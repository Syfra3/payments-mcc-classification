"""
Pydantic schemas for request/response validation.
"""

from typing import Any, Generic, TypeVar, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

# ==================== Merchant Schemas ====================

class MerchantCreateRequest(BaseModel):
    """Request schema for creating a merchant."""
    name: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., min_length=1, max_length=50)
    mcc_codes: Optional[list[str]] = Field(default=None)
    logo_url: Optional[str] = Field(default=None)
    metadata: Optional[dict[str, Any]] = Field(default=None)

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class MerchantUpdateRequest(BaseModel):
    """Request schema for updating a merchant."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    logo_url: Optional[str] = Field(default=None)
    weight: Optional[float] = Field(default=None, ge=0.0)
    metadata: Optional[dict[str, Any]] = Field(default=None)

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class MerchantResponse(BaseModel):
    """Response schema for merchant entity."""
    id: UUID
    name: str
    provider: str
    logo_url: Optional[str] = None
    weight: float
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class MerchantListResponse(BaseModel):
    """Response schema for merchant list with pagination."""
    items: list[MerchantResponse]
    total: int
    skip: int
    limit: int

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


# ==================== MCC Schemas ====================

class MccCreateRequest(BaseModel):
    """Request schema for creating an MCC."""
    code: str = Field(..., min_length=1, max_length=10)
    description: str = Field(..., min_length=1, max_length=255)
    category_id: Optional[UUID] = Field(default=None)

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class MccUpdateRequest(BaseModel):
    """Request schema for updating an MCC."""
    description: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category_id: Optional[UUID] = Field(default=None)

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class MccResponse(BaseModel):
    """Response schema for MCC entity."""
    id: UUID
    code: str
    description: str
    category_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class MccListResponse(BaseModel):
    """Response schema for MCC list with pagination."""
    items: list[MccResponse]
    total: int
    skip: int
    limit: int

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


# ==================== Category Schemas ====================

class CategoryCreateRequest(BaseModel):
    """Request schema for creating a category."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class CategoryResponse(BaseModel):
    """Response schema for category entity."""
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


# ==================== External Merchant Schemas ====================

class ExternalMerchantCreateRequest(BaseModel):
    """Request schema for registering an external merchant."""
    provider: str = Field(..., min_length=1, max_length=50)
    provider_id: str = Field(..., min_length=1, max_length=255)
    raw_data: dict[str, Any]

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class ExternalMerchantResponse(BaseModel):
    """Response schema for external merchant entity."""
    id: UUID
    provider: str
    provider_id: str
    merchant_id: Optional[UUID] = None
    raw_data: dict[str, Any]
    normalized_data: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class ExternalMerchantListResponse(BaseModel):
    """Response schema for external merchant list with pagination."""
    items: list[ExternalMerchantResponse]
    total: int
    skip: int
    limit: int

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


# ==================== Embedding Search Schemas ====================

class EmbeddingSearchRequest(BaseModel):
    """Request schema for embedding similarity search."""
    query: str = Field(..., min_length=1, max_length=1000)
    resource_types: list[str] = Field(default=["merchant", "mcc"])
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    limit: int = Field(default=10, ge=1, le=100)

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class EmbeddingSearchResponse(BaseModel):
    """Response schema for embedding search results."""
    merchants: list[dict[str, Any]] = Field(default_factory=list)
    mccs: list[dict[str, Any]] = Field(default_factory=list)

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


# ==================== Outbox Event Schemas ====================

class OutboxEventResponse(BaseModel):
    """Response schema for outbox event."""
    id: UUID
    event_type: str
    aggregate_id: Optional[UUID] = None
    aggregate_type: str
    payload: dict[str, Any]
    status: str
    retry_count: int
    next_retry_at: Optional[datetime] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class OutboxEventListResponse(BaseModel):
    """Response schema for outbox event list with pagination."""
    items: list[OutboxEventResponse]
    total: int
    skip: int
    limit: int

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


# ==================== Pipeline Result Schemas ====================

class PipelineResultResponse(BaseModel):
    """Response schema for pipeline execution result."""
    merchant_id: Optional[UUID] = None
    steps_completed: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    status: str  # "success" | "partial" | "failed"
    duration_ms: int

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class ValidationResultResponse(BaseModel):
    """Response schema for validation result."""
    valid: bool
    errors: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


# ==================== Error Schemas ====================

class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error_code: str
    message: str
    details: Optional[dict[str, Any]] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


# ==================== Utility Type Var ====================

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response schema."""
    items: list[T]
    total: int
    skip: int
    limit: int

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True
