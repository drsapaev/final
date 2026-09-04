"""
Regression: ObservabilityMiddleware read request.scope["route"] BEFORE
call_next — the route is resolved into the scope only during routing, so
metrics/logs always recorded the raw request URL instead of the route
template (Sentry alerts were being attributed to raw probe URLs like
/api/v1/payment-methods instead of real endpoints). The route is now read
after call_next; slow requests (> p95 SLA threshold) are additionally
logged as request.slow with the route template.
"""

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.observability_middleware import ObservabilityMiddleware


def test_metrics_log_records_route_template(caplog):
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/api/v1/widgets/{widget_id}")
    def get_widget(widget_id: int) -> dict:
        return {"ok": True}

    with caplog.at_level(logging.INFO, logger="app.middleware.observability_middleware"):
        client = TestClient(app)
        resp = client.get("/api/v1/widgets/42")
    assert resp.status_code == 200

    completed = [
        r for r in caplog.records if r.getMessage() == "request.completed"
    ]
    assert completed, "request.completed log expected"
    # Pre-fix this was the raw URL "/api/v1/widgets/42"
    assert completed[-1].path == "/api/v1/widgets/{widget_id}"
