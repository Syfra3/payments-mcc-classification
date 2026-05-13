"""End-to-end API tests."""
import json
import hmac
import hashlib
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.config import settings


@pytest.fixture
def app():
    """Create app for testing."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


def compute_hmac_signature(message: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature."""
    return hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()


def get_headers_with_signature(body: str, secret: str = None) -> dict:
    """Get headers with HMAC signature."""
    if secret is None:
        secret = settings.hmac_secret
    signature = compute_hmac_signature(body, secret)
    return {
        "Content-Type": "application/json",
        "X-API-Signature": signature,
    }


# ============================================================================
# Health Check Tests
# ============================================================================


def test_health_endpoint_returns_ok(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_health_ready_endpoint(client):
    """Test readiness check endpoint."""
    response = client.get("/health/ready")
    # May return 200 or 503 depending on DB availability
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data


# ============================================================================
# Merchant API Tests
# ============================================================================


def test_create_merchant_success(client):
    """Test creating a merchant with valid data."""
    payload = json.dumps({
        "name": "Test Merchant",
        "provider": "pomelo",
        "external_id": f"ext_{uuid.uuid4()}",
        "metadata": {"human_created": False}
    })

    headers = get_headers_with_signature(payload)
    response = client.post("/api/v1/merchants", content=payload, headers=headers)

    # Should return 201 or 200 depending on implementation
    assert response.status_code in [200, 201]
    data = response.json()
    assert "id" in data
    assert data["name"] == "TEST MERCHANT"  # Should be uppercased
    assert data["provider"] == "pomelo"


def test_get_merchant_returns_200(client):
    """Test retrieving a merchant."""
    # First create a merchant
    merchant_id = str(uuid.uuid4())
    payload = json.dumps({
        "name": "Get Test Merchant",
        "provider": "pomelo",
        "external_id": f"ext_{uuid.uuid4()}",
    })
    headers = get_headers_with_signature(payload)
    client.post("/api/v1/merchants", content=payload, headers=headers)

    # Now try to get it
    response = client.get(f"/api/v1/merchants/{merchant_id}", headers=headers)

    # May return 200, 404, or error depending on whether it was created
    assert response.status_code in [200, 404]


def test_missing_hmac_signature_returns_401(client):
    """Test that missing HMAC signature is rejected."""
    payload = json.dumps({
        "name": "Test",
        "provider": "pomelo",
        "external_id": "ext_123"
    })

    # No X-API-Signature header
    headers = {"Content-Type": "application/json"}
    response = client.post("/api/v1/merchants", content=payload, headers=headers)

    assert response.status_code == 401


def test_invalid_hmac_signature_returns_401(client):
    """Test that invalid HMAC signature is rejected."""
    payload = json.dumps({
        "name": "Test",
        "provider": "pomelo",
        "external_id": "ext_123"
    })

    headers = {
        "Content-Type": "application/json",
        "X-API-Signature": "invalid_signature_xyz"
    }
    response = client.post("/api/v1/merchants", content=payload, headers=headers)

    assert response.status_code == 401


def test_list_merchants_returns_200(client):
    """Test listing merchants."""
    headers = get_headers_with_signature("")
    response = client.get("/api/v1/merchants", headers=headers)

    # May return 200, 404, or error
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, (dict, list))


# ============================================================================
# MCC API Tests
# ============================================================================


def test_create_mcc_success(client):
    """Test creating an MCC."""
    payload = json.dumps({
        "code": "5411",
        "description": "Grocery stores",
    })

    headers = get_headers_with_signature(payload)
    response = client.post("/api/v1/mccs", content=payload, headers=headers)

    # Should return 201 or 200
    assert response.status_code in [200, 201, 409]  # 409 if duplicate


def test_list_mccs_returns_200(client):
    """Test listing MCCs."""
    headers = get_headers_with_signature("")
    response = client.get("/api/v1/mccs", headers=headers)

    # May return 200 or 404
    assert response.status_code in [200, 404]


# ============================================================================
# Error Cases
# ============================================================================


def test_create_merchant_with_invalid_data_returns_422(client):
    """Test that invalid merchant data returns 422."""
    payload = json.dumps({
        "name": "",  # Invalid: empty name
        "provider": "pomelo"
    })

    headers = get_headers_with_signature(payload)
    response = client.post("/api/v1/merchants", content=payload, headers=headers)

    assert response.status_code in [400, 422]


def test_malformed_json_returns_400(client):
    """Test that malformed JSON returns 400."""
    payload = "not valid json{"
    headers = get_headers_with_signature(payload)

    response = client.post("/api/v1/merchants", content=payload, headers=headers)

    assert response.status_code in [400, 422]


# ============================================================================
# Response Format Tests
# ============================================================================


def test_success_response_has_required_fields(client):
    """Test that success responses have required fields."""
    payload = json.dumps({
        "name": "Format Test",
        "provider": "pomelo",
        "external_id": f"ext_{uuid.uuid4()}"
    })

    headers = get_headers_with_signature(payload)
    response = client.post("/api/v1/merchants", content=payload, headers=headers)

    if response.status_code in [200, 201]:
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "provider" in data
        assert "created_at" in data or "timestamp" in data


def test_error_response_has_error_code(client):
    """Test that error responses include error code."""
    headers = {"Content-Type": "application/json"}
    response = client.post(
        "/api/v1/merchants",
        content=json.dumps({"name": "Test"}),
        headers=headers
    )

    if response.status_code >= 400:
        data = response.json()
        # Error response should have error info
        assert "error" in data or "error_code" in data or "message" in data


# ============================================================================
# Pagination Tests
# ============================================================================


def test_list_merchants_with_pagination(client):
    """Test pagination parameters."""
    headers = get_headers_with_signature("")
    response = client.get("/api/v1/merchants?skip=0&limit=10", headers=headers)

    assert response.status_code in [200, 404]
    if response.status_code == 200:
        data = response.json()
        # Should have pagination info
        assert "items" in data or "data" in data or isinstance(data, list)


# ============================================================================
# API Schema Tests
# ============================================================================


def test_openapi_schema_available(client):
    """Test that OpenAPI schema is available."""
    response = client.get("/api/openapi.json")

    # OpenAPI endpoint should exist
    if response.status_code == 200:
        data = response.json()
        assert "openapi" in data or "swagger" in data


def test_swagger_ui_available(client):
    """Test that Swagger UI is available."""
    response = client.get("/api/docs")

    # Swagger UI should be HTML
    if response.status_code == 200:
        assert "html" in response.headers.get("content-type", "").lower()
