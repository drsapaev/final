"""Mobile-contract tests (PR-4): pin the Android client's backend surface.

Basis: the full Retrofit surface of drsapaev/apkfinal (MobileApiService +
ApiService) checked against the live FastAPI route table. 40 of 41 client
endpoints must resolve; the only declared-but-uncalled path (GET /users) is
documented in the PR body as mobile-repo backlog, intentionally not served.

Layers covered here:
1. Route-table contract: every (method, path-template) the mobile app calls
   resolves in app.routes (path params normalized, canonical routes included).
2. Mount-order regression pins: static routes must keep winning over the new
   parametric aliases (registration order is behavior).
3. Functional pins: alias handlers share the canonical implementation and the
   mobile self-test endpoint pins the chat server-side (no relay surface).
"""

import re

import pytest
from fastapi.routing import APIRoute
from starlette.routing import Match

from app.main import app

# ---------------------------------------------------------------------------
# 1. Route-table contract
# ---------------------------------------------------------------------------

# The 41 Retrofit calls of the Android client (paths as the client requests
# them; path template params normalized below). GET /users is declared in the
# client but never called - it is intentionally absent from this list.
MOBILE_CONTRACT_ENDPOINTS = [
    ("POST", "/api/v1/authentication/login"),
    ("POST", "/api/v1/authentication/refresh"),
    ("POST", "/api/v1/authentication/logout"),
    ("GET", "/api/v1/authentication/profile"),
    ("POST", "/api/v1/2fa/verify"),
    ("POST", "/api/v1/2fa/recovery/request"),
    ("POST", "/api/v1/2fa/recovery/verify"),
    ("GET", "/api/v1/mobile/patients/me"),
    ("PUT", "/api/v1/mobile/profile"),
    ("POST", "/api/v1/mobile/profile/avatar"),
    ("GET", "/api/v1/mobile/appointments/upcoming"),
    ("POST", "/api/v1/mobile/appointments/book"),
    ("POST", "/api/v1/mobile/appointments/cancel"),
    ("POST", "/api/v1/mobile/appointments/reschedule"),
    ("POST", "/api/v1/telegram-integration/send-notification"),
    ("GET", "/api/v1/mobile/queues/my-position"),
    ("GET", "/api/v1/mobile/lab/results"),
    ("GET", "/api/v1/mobile/notifications"),
    ("POST", "/api/v1/mobile/notifications/{notification_id}/read"),
    ("GET", "/api/v1/mobile/settings/notifications"),
    ("PUT", "/api/v1/mobile/settings/notifications"),
    ("GET", "/api/v1/mobile/stats"),
    ("GET", "/api/v1/mobile/doctors"),
    ("GET", "/api/v1/mobile/doctors/{id}/schedule"),
    ("GET", "/api/v1/appointments/"),
    ("POST", "/api/v1/appointments/"),
    ("PUT", "/api/v1/appointments/{id}"),
    ("GET", "/api/v1/patients/"),
    ("POST", "/api/v1/doctor/queue/{entry_id}/call"),
    ("POST", "/api/v1/doctor/queue/{entry_id}/complete"),
    ("POST", "/api/v1/doctor/queue/{entry_id}/start-visit"),
    ("GET", "/api/v1/emr/{visit_id}"),
    ("POST", "/api/v1/emr/{visit_id}"),
    ("POST", "/api/v1/online-queue/entries/{entry_id}/cancel"),
    ("GET", "/api/v1/visits"),
    ("GET", "/api/v1/visits/{visit_id}"),
    ("GET", "/api/v1/queue/available-specialists"),
    ("GET", "/api/v1/queue/status/{specialist_id}"),
    ("PUT", "/api/v1/queue/move-entry"),
    ("POST", "/api/v1/registrar-integration/queue/entries/batch"),
]


def _normalize(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path).rstrip("/")


def _registered() -> set[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            seen.add((method, _normalize(route.path)))
    return seen


def test_mobile_contract_all_client_endpoints_resolve() -> None:
    registered = _registered()
    missing = [
        (method, path)
        for method, path in MOBILE_CONTRACT_ENDPOINTS
        if (method, _normalize(path)) not in registered
    ]
    assert not missing, f"Mobile contract endpoints missing on backend: {missing}"


# ---------------------------------------------------------------------------
# 2. Mount-order regression pins (static routes must beat parametric aliases)
# ---------------------------------------------------------------------------


def _first_full_match(method: str, path: str) -> str | None:
    for route in app.routes:
        match = route.matches(
            scope={"type": "http", "method": method, "path": path}
        )
        if match[0] == Match.FULL:
            return getattr(route, "name", None)
    return None


@pytest.mark.parametrize(
    ("method", "path", "expected_name"),
    [
        ("GET", "/api/v1/emr/templates", "get_emr_templates"),
        ("GET", "/api/v1/emr/templates/user", "get_user_templates"),
        ("GET", "/api/v1/emr/doctor-history", "get_doctor_history"),
        ("GET", "/api/v1/emr/patient/5", "get_patient_emrs"),
        ("GET", "/api/v1/visits/info/anytoken", "get_visit_info_by_token"),
    ],
)
def test_static_routes_win_over_parametric_aliases(
    method: str, path: str, expected_name: str
) -> None:
    assert _first_full_match(method, path) == expected_name, (
        f"{method} {path} must resolve to the static handler {expected_name}"
    )


def test_visits_detail_alias_resolves_to_alias_handler() -> None:
    assert _first_full_match("GET", "/api/v1/visits/123") == "get_visit_mobile_alias"
    assert _first_full_match("GET", "/api/v1/visits/visits/123") == "get_visit"


# ---------------------------------------------------------------------------
# 3. Functional pins
# ---------------------------------------------------------------------------


def test_visits_detail_alias_exposes_service_id(
    client, db, test_visit, registrar_token
) -> None:
    from app.models.visit import VisitService

    service_row = VisitService(
        visit_id=test_visit.id,
        service_id=42,
        code="CONS",
        name="Consultation",
        qty=1,
        price=100,
    )
    db.add(service_row)
    db.commit()

    headers = {"Authorization": f"Bearer {registrar_token}"}

    alias = client.get(f"/api/v1/visits/{test_visit.id}", headers=headers)
    assert alias.status_code == 200
    alias_body = alias.json()
    assert alias_body["visit"]["id"] == test_visit.id
    assert alias_body["services"], "services list must not be empty"
    assert alias_body["services"][0]["service_id"] == 42
    assert alias_body["services"][0]["id"] == service_row.id

    canonical = client.get(
        f"/api/v1/visits/visits/{test_visit.id}", headers=headers
    )
    assert canonical.status_code == 200
    assert canonical.json() == alias_body, "alias must return the canonical payload"


def test_queue_move_entry_alias_shares_canonical_handler(
    client, db, registrar_token, monkeypatch
) -> None:
    from app.api.v1.endpoints import queue_reorder as qr_module

    calls: list[dict] = []

    class _FakeService:
        def __init__(self, db_session):
            self.db_session = db_session

        def move_queue_entry(self, *, entry_id, new_position, current_user):
            calls.append(
                {"entry_id": entry_id, "new_position": new_position}
            )
            return "moved", 3, {"queue_id": 1}

    monkeypatch.setattr(qr_module, "QueueReorderApiService", _FakeService)

    headers = {"Authorization": f"Bearer {registrar_token}"}
    payload = {"entry_id": 7, "new_position": 2}

    response = client.put("/api/v1/queue/move-entry", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "moved"
    assert body["updated_entries"] == 3
    assert calls == [{"entry_id": 7, "new_position": 2}]

    canonical = client.put(
        "/api/v1/queue/reorder/move-entry", json=payload, headers=headers
    )
    assert canonical.status_code == 200
    assert canonical.json() == body


def test_queue_move_entry_alias_rejects_patient_role(
    client, patient_token
) -> None:
    headers = {"Authorization": f"Bearer {patient_token}"}
    response = client.put(
        "/api/v1/queue/move-entry",
        json={"entry_id": 7, "new_position": 2},
        headers=headers,
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Telegram mobile self-test endpoint
# ---------------------------------------------------------------------------


class _FakeBotService:
    def __init__(self, send_result: bool = True):
        self.active = True
        self.bot_token = "canonical-token"
        self.initialize_calls = 0
        self.send_result = send_result
        self.sent: list[tuple[int, str]] = []

    async def initialize(self, db):
        self.initialize_calls += 1
        self.bot_token = "canonical-token"
        return True

    async def send_plain_message(self, chat_id: int, text: str) -> bool:
        self.sent.append((chat_id, text))
        return self.send_result


@pytest.fixture
def patient_user(db):
    from app.core.security import get_password_hash
    from app.models.user import User

    user = db.query(User).filter(User.username == "patient_test").first()
    if not user:
        user = User(
            username="patient_test",
            email="patient@test.com",
            hashed_password=get_password_hash("patient123"),
            role="Patient",
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_mobile_self_test_requires_auth(client) -> None:
    response = client.post(
        "/api/v1/telegram-integration/send-notification",
        json={"chat_id": "777", "message": "hi"},
    )
    assert response.status_code in {401, 403}


def test_mobile_self_test_without_link_is_404(
    client, patient_token
) -> None:
    response = client.post(
        "/api/v1/telegram-integration/send-notification",
        json={"chat_id": "777", "message": "hi"},
        headers=_auth_headers(patient_token),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "telegram_not_linked"


def test_mobile_self_test_pins_own_chat_and_ignores_client_chat(
    client, db, patient_user, patient_token, monkeypatch
) -> None:
    from app.api.v1.endpoints import telegram_integration as ti_module
    from app.models.telegram_config import TelegramUser

    link = TelegramUser(
        user_id=patient_user.id,
        chat_id=777,
        language_code="ru",
        active=True,
        blocked=False,
    )
    db.add(link)
    db.commit()

    fake = _FakeBotService()

    async def _fake_get_service():
        return fake

    monkeypatch.setattr(ti_module, "get_telegram_bot_service", _fake_get_service)
    monkeypatch.setattr(
        ti_module, "resolve_patient_bot_token", lambda db: "canonical-token"
    )

    # Client-supplied chat_id points at a foreign chat - it MUST be ignored.
    response = client.post(
        "/api/v1/telegram-integration/send-notification",
        json={"chat_id": "999999", "message": "spoofed", "parse_mode": "HTML"},
        headers=_auth_headers(patient_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["chat_id"] == 777
    assert fake.sent == [(777, ti_module._MOBILE_SELF_TEST_TEXT)]


def test_mobile_self_test_send_failure_is_503(
    client, db, patient_user, patient_token, monkeypatch
) -> None:
    from app.api.v1.endpoints import telegram_integration as ti_module
    from app.models.telegram_config import TelegramUser

    db.add(
        TelegramUser(
            user_id=patient_user.id,
            chat_id=777,
            language_code="ru",
            active=True,
            blocked=False,
        )
    )
    db.commit()

    fake = _FakeBotService(send_result=False)

    async def _fake_get_service():
        return fake

    monkeypatch.setattr(ti_module, "get_telegram_bot_service", _fake_get_service)
    monkeypatch.setattr(
        ti_module, "resolve_patient_bot_token", lambda db: "canonical-token"
    )

    response = client.post(
        "/api/v1/telegram-integration/send-notification",
        json={"chat_id": "777"},
        headers=_auth_headers(patient_token),
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "telegram_send_failed"


def test_mobile_self_test_reinitializes_on_stale_credential(
    client, db, patient_user, patient_token, monkeypatch
) -> None:
    from app.api.v1.endpoints import telegram_integration as ti_module
    from app.models.telegram_config import TelegramUser

    db.add(
        TelegramUser(
            user_id=patient_user.id,
            chat_id=777,
            language_code="ru",
            active=True,
            blocked=False,
        )
    )
    db.commit()

    fake = _FakeBotService()
    fake.bot_token = "superseded-token"

    async def _fake_get_service():
        return fake

    monkeypatch.setattr(ti_module, "get_telegram_bot_service", _fake_get_service)
    monkeypatch.setattr(
        ti_module, "resolve_patient_bot_token", lambda db: "canonical-token"
    )

    response = client.post(
        "/api/v1/telegram-integration/send-notification",
        json={"chat_id": "777"},
        headers=_auth_headers(patient_token),
    )
    assert response.status_code == 200
    assert fake.initialize_calls == 1
