"""Request validation for report delivery; HTTP/DB behavior is tested in
tests/integration/test_telegram_notifications_private_scope.py.
"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.endpoints.telegram_notifications import router as telegram_router

SYNTHETIC_ADMIN = SimpleNamespace(id=1, role="Admin", is_superuser=False,
                                  is_active=True, username="synthetic-admin")

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(telegram_router, prefix="/telegram")
    app.dependency_overrides[get_current_user] = lambda: SYNTHETIC_ADMIN
    app.dependency_overrides[get_db] = lambda: object()
    return TestClient(app)


class TestLegacyRouteRejectsOldFrontendShape:
    def test_old_frontend_body_shape_is_rejected_422_before_business_logic(self, client):
        """The exact pre-fix frontend request: JSON body with instance_id."""
        response = client.post(
            "/telegram/send-lab-results",
            json={"patient_id": 444, "instance_id": 91},
        )
        assert response.status_code == 422, (
            "the legacy route must reject the old frontend JSON body at "
            "validation (patient_id/lab_result_ids are query parameters) — "
            "this is the LABN-FE-001 contract break"
        )


# ---------------------------------------------------------------------------
# New route: validation contract.
# ---------------------------------------------------------------------------


class TestNewRouteValidationContract:
    def test_missing_body_is_rejected_422(self, client):
        response = client.post("/telegram/send-lab-report-instance")
        assert response.status_code == 422

    def test_legacy_instance_id_field_name_is_rejected_422(self, client):
        """A wrong-shape request (the legacy field name) must fail readable
        validation instead of silently mapping unrelated ID spaces."""
        response = client.post(
            "/telegram/send-lab-report-instance",
            json={"patient_id": 444, "instance_id": 91},
        )
        assert response.status_code == 422
        body = response.json()
        assert any("report_instance_id" in str(err.get("loc", [])) for err in body["detail"])

    def test_legacy_lab_result_ids_shape_is_rejected_422(self, client):
        response = client.post(
            "/telegram/send-lab-report-instance",
            json={"patient_id": 444, "lab_result_ids": [1, 2]},
        )
        assert response.status_code == 422
