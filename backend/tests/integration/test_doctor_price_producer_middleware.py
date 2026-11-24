"""Doctor price credentials and DB idempotency must bypass cached responses."""
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.middleware.idempotency_middleware import IdempotencyMiddleware


def _app():
    seen = []

    async def endpoint(request):
        seen.append((request.url.path, str(request.url.query), request.headers.get("Idempotency-Key")))
        return JSONResponse({"count": len(seen), "token": "synthetic-token"})

    app = Starlette(routes=[
        Route("/api/v1/doctor/visits/schedule-next", endpoint, methods=["POST"]),
        Route("/api/v1/doctor/visits/{visit_id:int}/add-service", endpoint, methods=["PUT"]),
        Route("/api/v1/visits/{visit_id:int}/confirmation-reissue", endpoint, methods=["POST"]),
    ])
    app.add_middleware(IdempotencyMiddleware)
    return app, seen


def test_schedule_next_passes_same_key_to_handler_every_time_without_caching_token(monkeypatch):
    monkeypatch.setattr(IdempotencyMiddleware, "_verified_principal", lambda *_: (_ for _ in ()).throw(AssertionError("generic middleware must be bypassed")))
    app, seen = _app()
    with TestClient(app) as client:
        a = client.post("/api/v1/doctor/visits/schedule-next", headers={"Idempotency-Key": "test-key"}, json={"patient_id": 1})
        b = client.post("/api/v1/doctor/visits/schedule-next", headers={"Idempotency-Key": "test-key"}, json={"patient_id": 1})
    assert a.status_code == b.status_code == 200
    assert a.json()["count"] == 1 and b.json()["count"] == 2
    assert [row[2] for row in seen] == ["test-key", "test-key"]
    assert a.headers.get("cache-control") == b.headers.get("cache-control") == "no-store"


def test_add_service_does_not_cache_changed_query_with_identical_body_and_key(monkeypatch):
    monkeypatch.setattr(IdempotencyMiddleware, "_verified_principal", lambda *_: (_ for _ in ()).throw(AssertionError("generic middleware must be bypassed")))
    app, seen = _app()
    with TestClient(app) as client:
        a = client.put("/api/v1/doctor/visits/12/add-service?service_id=1&custom_price=0", headers={"Idempotency-Key": "test-key"})
        b = client.put("/api/v1/doctor/visits/12/add-service?service_id=2&custom_price=7", headers={"Idempotency-Key": "test-key"})
    assert a.status_code == b.status_code == 200
    assert len(seen) == 2 and seen[0][1] != seen[1][1]
    assert a.json()["count"] == 1 and b.json()["count"] == 2


def test_doctor_price_key_is_bounded_before_passing_handler():
    app, seen = _app()
    with TestClient(app) as client:
        response = client.post("/api/v1/doctor/visits/schedule-next", headers={"Idempotency-Key": "x" * 129})
    assert response.status_code == 400
    assert not seen


def test_confirmation_reissue_never_replays_generic_cache(monkeypatch):
    monkeypatch.setattr(IdempotencyMiddleware, "_verified_principal", lambda *_: (_ for _ in ()).throw(AssertionError("generic middleware must be bypassed")))
    app, seen = _app()
    with TestClient(app) as client:
        first = client.post("/api/v1/visits/12/confirmation-reissue", headers={"Idempotency-Key": "opaque-key"})
        second = client.post("/api/v1/visits/12/confirmation-reissue", headers={"Idempotency-Key": "opaque-key"})
    assert first.status_code == second.status_code == 200
    assert [row[2] for row in seen] == ["opaque-key", "opaque-key"]
    assert first.json()["count"] == 1 and second.json()["count"] == 2
    assert first.headers.get("cache-control") == second.headers.get("cache-control") == "no-store"
