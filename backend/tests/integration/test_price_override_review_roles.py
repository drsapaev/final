"""HTTP role boundary and doctorless requests in the review queue."""

import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.api import trusted_financial_auth
from app.api.v1.endpoints import dental
from app.api.v1.endpoints.registrar_wizard import _cart
from app.db.trusted_schema import TrustedSchemaUnavailable
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.service import Service
from app.models.visit import Visit, VisitService
from tests.conftest import mint_access_token
from tests.integration.test_derma_price_override_integrity import _create_user


def _headers(user):
    return {"Authorization": f"Bearer {mint_access_token(user)}"}


@pytest.mark.parametrize("route", ["registrar", "dental"])
@pytest.mark.parametrize("role,active,expected", [
    ("SuperAdmin", True, 200), ("Admin", True, 200), ("Registrar", True, 200),
    ("Doctor", True, 403), ("SuperAdmin", False, 403),
])
def test_review_routes_enforce_active_canonical_roles(client, db_session, monkeypatch, route, role, active, expected):
    user = _create_user(db_session, role=role, label="review-role")
    headers = _headers(user)
    if not active:
        user.is_active = False
        db_session.commit()
    transition = Mock(return_value=SimpleNamespace(id=123, status="rejected"))
    monkeypatch.setattr(_cart.PriceOverrideApprovalService, "process", transition)
    dental_transition = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(dental.DentalApiService, "approve_price_override", dental_transition)
    if route == "registrar":
        response = client.post("/api/v1/registrar/price-override/approve", headers=headers,
                               json={"override_id": 123, "action": "reject", "rejection_reason": "synthetic"})
    else:
        response = client.put("/api/v1/dental/price-override/123/approve", headers=headers,
                              json={"action": "reject", "rejection_reason": "synthetic"})
    assert response.status_code == expected, response.text
    if expected == 403:
        transition.assert_not_called()
        dental_transition.assert_not_awaited()


def test_doctorless_admin_request_is_visible_to_superadmin(client, db_session, test_patient):
    admin = _create_user(db_session, role="SuperAdmin", label="review-list")
    service = Service(code=f"R{uuid4().hex[:12]}", name="Synthetic", price=Decimal("100.00"),
                      active=True, allow_doctor_price_override=False, duration_minutes=10)
    db_session.add(service)
    db_session.flush()
    visit = Visit(patient_id=test_patient.id, doctor_id=None, visit_date=date.today(),
                  status="open", confirmation_context_epoch=1)
    db_session.add(visit)
    db_session.flush()
    line = VisitService(visit_id=visit.id, service_id=service.id, name="Synthetic",
                        qty=1, price=Decimal("100.00"), currency="UZS")
    db_session.add(line)
    db_session.flush()
    override = DoctorPriceOverride(
        visit_id=visit.id, doctor_id=None, service_id=service.id, target_scope="visit_service",
        target_visit_service_id=line.id, original_price=Decimal("100.00"),
        visit_price_before=Decimal("100.00"), new_price=Decimal("75.00"),
        reason="Synthetic", status="pending", requester_type="admin",
        requester_user_id=admin.id, requester_user_id_snapshot=admin.id,
        requester_auth_epoch=admin.auth_epoch,
    )
    db_session.add(override)
    db_session.commit()
    response = client.get("/api/v1/registrar/price-overrides", headers=_headers(admin))
    assert response.status_code == 200, response.text
    record = next(item for item in response.json() if item["id"] == override.id)
    assert record["doctor_name"] == "Не назначен" and record["doctor_specialty"] == ""


@pytest.mark.parametrize("role,expected", [("SuperAdmin", 200), ("Registrar", 200), ("Doctor", 403)])
def test_dental_review_queue_has_same_roles(client, db_session, role, expected):
    user = _create_user(db_session, role=role, label="dental-review-list")
    response = client.get("/api/v1/dental/price-overrides/pending", headers=_headers(user))
    assert response.status_code == expected, response.text


@pytest.mark.parametrize("role,active,expected", [
    ("Admin", True, 200), ("SuperAdmin", True, 200),
    ("Registrar", True, 403), ("SuperAdmin", False, 403),
])
def test_all_free_review_requires_active_admin(client, db_session, role, active, expected):
    user = _create_user(db_session, role=role, label="all-free-review")
    headers = _headers(user)
    if not active:
        user.is_active = False
        db_session.commit()
    response = client.get("/api/v1/admin/all-free-requests", headers=headers)
    assert response.status_code == expected, response.text


@pytest.mark.parametrize("path,method", [
    ("/api/v1/registrar/price-override/approve", "post"),
    ("/api/v1/dental/price-override/123/approve", "put"),
    ("/api/v1/admin/all-free-approve", "post"),
])
def test_schema_failure_stops_before_authentication(client, monkeypatch, path, method):
    authenticate = AsyncMock()
    monkeypatch.setattr(trusted_financial_auth.deps, "get_current_user", authenticate)
    def refuse(*_args, **_kwargs):
        raise TrustedSchemaUnavailable("synthetic secret should not be returned")
    monkeypatch.setattr(trusted_financial_auth, "pin_application_schema", refuse)
    response = getattr(client, method)(path, headers={"Authorization": "Bearer synthetic"}, json={})
    assert response.status_code == 503
    assert "synthetic secret" not in response.text
    authenticate.assert_not_awaited()


def test_first_engine_connection_initializes_schema_before_authentication(monkeypatch):
    dialect = SimpleNamespace(name="postgresql", default_schema_name=None)
    db = Mock()
    db.get_bind.return_value.dialect = dialect
    calls = []

    def connect():
        calls.append("connect")
        dialect.default_schema_name = "synthetic_app"

    db.connection.side_effect = connect
    monkeypatch.setattr(trusted_financial_auth.settings, "TRUSTED_DB_SCHEMA", "synthetic_app")
    monkeypatch.setattr(trusted_financial_auth.settings, "TRUSTED_DB_SCHEMA_OWNER", "synthetic_owner")
    for name in ("DOCTOR_PRICE_DB_SCHEMA", "DOCTOR_PRICE_DB_SCHEMA_OWNER", "INVITATION_DB_SCHEMA", "INVITATION_DB_SCHEMA_OWNER"):
        monkeypatch.setattr(trusted_financial_auth.settings, name, None)
    actor = SimpleNamespace(id=1, role="Admin", is_active=True, is_superuser=False)
    async def authenticate(**_kwargs):
        calls.append("auth")
        return actor
    monkeypatch.setattr(trusted_financial_auth.deps, "get_current_user", authenticate)
    monkeypatch.setattr(trusted_financial_auth, "pin_application_schema", lambda *_a, **_kw: calls.append("pin"))
    assert asyncio.run(trusted_financial_auth._authenticate("synthetic", db, ("Admin",))) is actor
    assert calls == ["connect", "pin", "auth"]
