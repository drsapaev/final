"""Mobile-contract tests (PR-4): pin the Android client's backend surface.

Basis: the full Retrofit surface of drsapaev/apkfinal (MobileApiService +
ApiService) checked against the backend's published OpenAPI schema and live
behavior. 40 of 41 client endpoints must resolve; the only declared-but-
uncalled path (GET /users) is documented in the PR body as mobile-repo
backlog, intentionally not served.

Layers covered here:
1. Route-table contract via the OpenAPI schema: every (method, path-template)
   the mobile app calls is published by the backend (path params normalized).
   OpenAPI introspection is stable across FastAPI/Starlette versions (unlike
   manual app.routes matching, which broke with the _IncludedRouter model).
2. Registration-order behavior pins: static routes must keep winning over the
   new parametric aliases. Asserted behaviorally: a non-int segment that
   would 422 if the parametric alias captured it resolves through the static
   handler instead (auth gates answer 401/403, public handlers answer
   200/404).
3. Functional pins: alias handlers share the canonical implementation and the
   mobile self-test endpoint pins the chat server-side (no relay surface).
"""

import re

import pytest

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


def _published() -> set[tuple[str, str]]:
    schema = app.openapi()
    seen: set[tuple[str, str]] = set()
    for path, operations in (schema.get("paths") or {}).items():
        for method in operations:
            if method.lower() in {"head", "options", "parameters"}:
                continue
            seen.add((method.upper(), _normalize(path)))
    return seen


def test_mobile_contract_all_client_endpoints_resolve() -> None:
    published = _published()
    missing = [
        (method, path)
        for method, path in MOBILE_CONTRACT_ENDPOINTS
        if (method, _normalize(path)) not in published
    ]
    assert not missing, f"Mobile contract endpoints missing on backend: {missing}"


# ---------------------------------------------------------------------------
# 2. Registration-order behavior pins (static routes must beat parametric
#    aliases). Discriminator: if a parametric alias captured a static path,
#    the non-int segment would fail validation with 422; the static handler
#    instead answers with its own auth gate (401/403) or its normal result.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "forbidden"),
    [
        # Non-int segments that a parametric alias would 422 on if it won:
        ("GET", "/api/v1/emr/templates", {404, 422}),
        ("GET", "/api/v1/emr/templates/user", {404, 422}),
        # Mobile EMR alias / visit routes must be routed (auth gate answers):
        ("GET", "/api/v1/emr/123", {404, 422}),
        ("GET", "/api/v1/visits/123", {404, 422}),
        ("GET", "/api/v1/visits/visits/123", {404, 422}),
        # Public confirmation-info handler legitimately 404s on unknown
        # tokens - only parametric capture (422) would be a regression.
        ("GET", "/api/v1/visits/info/anytoken", {422}),
    ],
)
def test_static_and_alias_routes_resolve_without_parametric_capture(
    client, method: str, path: str, forbidden: set[int]
) -> None:
    response = getattr(client, method.lower())(path)
    assert response.status_code not in forbidden, (
        f"{method} {path} -> {response.status_code}: route must be registered "
        "and must not be captured by a parametric alias"
    )


def test_visit_confirmation_info_route_is_published() -> None:
    published = _published()
    assert ("GET", _normalize("/api/v1/visits/info/{token}")) in published


# ---------------------------------------------------------------------------
# 3. Functional pins
# ---------------------------------------------------------------------------


def test_visit_card_read_writes_patient_access_audit(
    client, db, test_visit, registrar_token
) -> None:
    """AGENTS.md threat model: 'Audit log on every patient read' — the mobile
    alias delegates to the canonical handler, so the shared audit fires once
    per request on both routes."""
    from app.models.patient_access_audit import PatientAccessAuditLog

    headers = {"Authorization": f"Bearer {registrar_token}"}
    response = client.get(f"/api/v1/visits/{test_visit.id}", headers=headers)
    assert response.status_code == 200

    rows = (
        db.query(PatientAccessAuditLog)
        .filter(
            PatientAccessAuditLog.subject_patient_id == test_visit.patient_id,
            PatientAccessAuditLog.resource_type == "visit",
            PatientAccessAuditLog.resource_id == str(test_visit.id),
            PatientAccessAuditLog.action == "view",
        )
        .all()
    )
    assert rows, "patient-read audit trail must be written for the visit card"


def test_visit_list_read_writes_batch_patient_access_audit(
    client, db, test_visit, registrar_token
) -> None:
    """List reads carry patient_id + clinical notes — batch audit trail for
    every returned subject on both canonical and mobile alias routes."""
    from app.models.patient_access_audit import PatientAccessAuditLog

    headers = {"Authorization": f"Bearer {registrar_token}"}
    response = client.get(
        f"/api/v1/visits?patient_id={test_visit.patient_id}", headers=headers
    )
    assert response.status_code == 200
    assert response.json(), "fixture visit must be returned"

    rows = (
        db.query(PatientAccessAuditLog)
        .filter(
            PatientAccessAuditLog.subject_patient_id == test_visit.patient_id,
            PatientAccessAuditLog.resource_type == "visit",
            PatientAccessAuditLog.action == "view",
        )
        .all()
    )
    assert rows, "batch patient-read audit trail must be written for the list"


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


def test_mobile_self_test_direct_link_beats_newer_patient_link(
    client, db, patient_user, patient_token, monkeypatch
) -> None:
    """Documented precedence: a direct user_id link always wins, even when a
    NEWER patient-domain link exists for the same user."""
    from datetime import date

    from app.api.v1.endpoints import telegram_integration as ti_module
    from app.models.patient import Patient
    from app.models.telegram_config import TelegramUser

    # AGENTS.md Synthetic data policy: SYNTHETIC- marker + DEV-DEMO phone
    # instead of a realistic name+phone pair (codex round-3 P1).
    patient = Patient(
        last_name="SYNTHETIC-PR4-Precedence",
        first_name="SYNTHETIC-Test",
        phone="DEV-DEMO-PR4-1",
        birth_date=date(1990, 1, 1),
        user_id=patient_user.id,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    direct = TelegramUser(
        user_id=patient_user.id,
        chat_id=555,
        language_code="ru",
        active=True,
        blocked=False,
    )
    db.add(direct)
    db.commit()
    db.refresh(direct)

    # Newer row on the patient-domain link must NOT steal the delivery.
    patient_link = TelegramUser(
        patient_id=patient.id,
        chat_id=888,
        language_code="ru",
        active=True,
        blocked=False,
    )
    db.add(patient_link)
    db.commit()

    fake = _FakeBotService()

    async def _fake_get_service():
        return fake

    monkeypatch.setattr(ti_module, "get_telegram_bot_service", _fake_get_service)
    monkeypatch.setattr(
        ti_module, "resolve_patient_bot_token", lambda db: "canonical-token"
    )

    response = client.post(
        "/api/v1/telegram-integration/send-notification",
        json={"chat_id": "888"},
        headers=_auth_headers(patient_token),
    )
    assert response.status_code == 200
    assert response.json()["chat_id"] == 555
    assert fake.sent == [(555, ti_module._MOBILE_SELF_TEST_TEXT)]


def test_mobile_self_test_rejects_inactive_link(
    client, db, patient_user, patient_token
) -> None:
    from app.models.telegram_config import TelegramUser

    db.add(
        TelegramUser(
            user_id=patient_user.id,
            chat_id=777,
            language_code="ru",
            active=False,
            blocked=False,
        )
    )
    db.commit()

    response = client.post(
        "/api/v1/telegram-integration/send-notification",
        json={"chat_id": "777"},
        headers=_auth_headers(patient_token),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "telegram_not_linked"


def test_mobile_self_test_rejects_disabled_bot(
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
    fake.active = False  # bot administratively disabled, token still stored

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
    assert response.json()["detail"] == "telegram_bot_disabled"
    assert fake.sent == []


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
