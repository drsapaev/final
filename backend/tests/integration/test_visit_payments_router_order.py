from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import visit_payments
from app.api.deps import get_db, get_current_user


def test_visit_payments_summary_route_dispatches_before_visit_id(monkeypatch):
    class FakeVisitPaymentApiService:
        def __init__(self, db):
            self.db = db

        def get_visit_payments_summary(self):
            return {"total": 1, "paid": 1}

    app = FastAPI()
    app.include_router(visit_payments.router)
    app.dependency_overrides[get_db] = lambda: object()
    # Use SimpleNamespace (not a dict) so attribute access in
    # app.core.security.require_roles (current_user.role,
    # current_user.is_superuser, current_user.id) works correctly.
    # This matches the production contract of get_current_user -> User
    # and the established override pattern in
    # tests/unit/test_messages_router_service_wiring.py.
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1,
        role="Admin",
        is_superuser=False,
    )

    monkeypatch.setattr(
        visit_payments,
        "VisitPaymentApiService",
        FakeVisitPaymentApiService,
    )

    response = TestClient(app).get("/visit-payments/summary")

    assert response.status_code == 200, response.text
    assert response.json() == {"total": 1, "paid": 1}
