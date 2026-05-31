from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import visit_payments


def test_visit_payments_summary_route_dispatches_before_visit_id(monkeypatch):
    class FakeVisitPaymentApiService:
        def __init__(self, db):
            self.db = db

        def get_visit_payments_summary(self):
            return {"total": 1, "paid": 1}

    app = FastAPI()
    app.include_router(visit_payments.router)
    app.dependency_overrides[visit_payments.get_db] = lambda: object()

    for route in app.routes:
        if getattr(route, "path", "") == "/visit-payments/summary":
            for dependency in route.dependant.dependencies:
                app.dependency_overrides[dependency.call] = lambda: {
                    "role": "Admin"
                }

    monkeypatch.setattr(
        visit_payments,
        "VisitPaymentApiService",
        FakeVisitPaymentApiService,
    )

    response = TestClient(app).get("/visit-payments/summary")

    assert response.status_code == 200, response.text
    assert response.json() == {"total": 1, "paid": 1}
