import json
from types import SimpleNamespace


class _FakeDbSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakeWsManager:
    def __init__(self):
        self.connect_calls = []
        self.disconnect_calls = []
        self.broadcast_calls = []

    async def connect(self, websocket, room):
        self.connect_calls.append((websocket, room))

    def disconnect(self, websocket, room):
        self.disconnect_calls.append((websocket, room))

    def broadcast(self, room, data):
        self.broadcast_calls.append((room, data))


async def _fake_authenticate_user(*_args, **_kwargs):
    return SimpleNamespace(id=19, username="doctor@test.local", role="Doctor")


def test_websocket_auth_optional_route_preserves_ping_and_connect_contract(
    client, monkeypatch
):
    from app.api.v1.endpoints import websocket_auth as websocket_auth_endpoints

    fake_db = _FakeDbSession()
    fake_manager = _FakeWsManager()

    monkeypatch.setattr(websocket_auth_endpoints, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(
        websocket_auth_endpoints,
        "authenticate_websocket_token",
        _fake_authenticate_user,
    )
    monkeypatch.setattr(websocket_auth_endpoints, "ws_manager", fake_manager)

    with client.websocket_connect(
        "/api/v1/ws-auth/ws/queue/optional-auth"
        "?department=lab&date=2026-03-13&token=test-token"
    ) as websocket:
        websocket.send_text(json.dumps({"type": "ping"}))
        response = websocket.receive_json()

    assert response["type"] == "pong"
    assert response["authenticated"] is True
    assert response["user"] == "doctor@test.local"
    assert [room for _websocket, room in fake_manager.connect_calls] == [
        "lab:2026-03-13"
    ]
    assert [room for _websocket, room in fake_manager.disconnect_calls] == [
        "lab:2026-03-13"
    ]
    assert fake_db.closed is True


def test_websocket_auth_authenticated_route_preserves_call_patient_broadcast(
    client, monkeypatch
):
    from app.api.v1.endpoints import websocket_auth as websocket_auth_endpoints

    fake_db = _FakeDbSession()
    fake_manager = _FakeWsManager()

    monkeypatch.setattr(websocket_auth_endpoints, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(
        websocket_auth_endpoints,
        "authenticate_websocket_token",
        _fake_authenticate_user,
    )
    monkeypatch.setattr(websocket_auth_endpoints, "ws_manager", fake_manager)
    monkeypatch.setattr(
        websocket_auth_endpoints.websocket_rate_limiter,
        "check_rate_limit",
        lambda _ip: (True, "ok"),
    )
    monkeypatch.setattr(
        websocket_auth_endpoints.websocket_rate_limiter,
        "record_connection",
        lambda _ip: None,
    )
    monkeypatch.setattr(
        websocket_auth_endpoints.websocket_rate_limiter,
        "remove_connection",
        lambda _ip: None,
    )

    with client.websocket_connect(
        "/api/v1/ws-auth/ws/queue/auth"
        "?department=lab&date=2026-03-13&token=test-token"
    ) as websocket:
        websocket.send_text(json.dumps({"type": "call_patient", "patient_id": "P-42"}))
        websocket.send_text(json.dumps({"type": "ping"}))
        response = websocket.receive_json()

    assert response["type"] == "pong"
    assert [room for _websocket, room in fake_manager.connect_calls] == [
        "lab:2026-03-13"
    ]
    assert [room for _websocket, room in fake_manager.disconnect_calls] == [
        "lab:2026-03-13"
    ]
    assert fake_manager.broadcast_calls

    room, payload = fake_manager.broadcast_calls[0]
    assert room == "lab:2026-03-13"
    assert payload["type"] == "patient_called"
    assert payload["patient_id"] == "P-42"
    assert payload["department"] == "lab"
    assert payload["caller"] == "doctor@test.local"
    assert fake_db.closed is True
