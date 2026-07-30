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
    app.dependency_overrides[get_current_user] = lambda: {
        "role": "Admin",
        "is_superuser": False,
        "id": 1,
    }

    monkeypatch.setattr(
        visit_payments,
        "VisitPaymentApiService",
        FakeVisitPaymentApiService,
    )

    response = TestClient(app).get("/visit-payments/summary")

    assert response.status_code == 200, response.text
    assert response.json() == {"total": 1, "paid": 1}
