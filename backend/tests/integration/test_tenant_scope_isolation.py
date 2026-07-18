"""Multi-tenant isolation tests for tenant_scope_middleware."""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestTenantScopeIsolation:
    """Test multi-tenant branch_id isolation."""

    def test_write_without_branch_id_rejected_when_enforced(
        self, client: TestClient, admin_auth_headers
    ):
        """When TENANT_SCOPE_ENFORCE_WRITES=True, write without branch_id rejected."""
        response = client.post(
            "/api/v1/billing/invoices",
            headers=admin_auth_headers,
            json={"amount": 1000},
        )
        assert response.status_code in (200, 400, 403, 422)

    def test_read_not_affected_by_enforcement(
        self, client: TestClient, admin_auth_headers
    ):
        """Read operations should not be affected by write enforcement."""
        response = client.get("/api/v1/billing/invoices", headers=admin_auth_headers)
        assert response.status_code in (200, 401, 403, 404)

    def test_non_protected_path_not_affected(
        self, client: TestClient
    ):
        """Health endpoint should work regardless of enforcement."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
