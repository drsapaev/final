"""QF-1 (queue entry operator attribution) — integration pins.

Foundation change under test (blueprint 2026-09-05):
- `called_by_user_id` becomes a REAL nullable FK column on queue_entries
  (it used to be a transient attribute set by QRQueueService.call_next_patient
  and persisted only via the GraphQL critical-audit path — Codex round-7 P1).
- `served_by_user_id` / `served_at` capture who completed the entry.
- REST call-next now writes the row-level critical audit row (GQL parity).
- RBAC/role vocabulary is intentionally NOT touched.

The persistence proofs deliberately use RAW SQL (bypassing the ORM identity
map): the pre-QF-1 transient attribute could satisfy ORM-level asserts on a
shared session (see test_qr_queue_full_update.py history), so only a
column-level SELECT proves the attribution is durable.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from app.core.security import get_password_hash
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User
from app.models.user_profile import UserAuditLog

BACKEND_ROOT = Path(__file__).resolve().parents[2]

CALL_NEXT_ROLES = 'require_roles("Admin", "Doctor", "Registrar")'
COMPLETE_ROUTE_MARK = '@router.post("/doctor/queue/{entry_id}/complete"'
EXPECTED_COMPLETE_ROLES = {
    "Admin",
    "Doctor",
    "Registrar",
    "Cashier",
    "cardio",
    "cardiology",
    "Cardiologist",
    "derma",
    "dentist",
    "Lab",
}
EXPECTED_QUEUE_MUTATION_ROLES = {
    "doctor",
    "cardio",
    "cardiology",
    "cardiologist",
    "derma",
    "dermatologist",
    "dentist",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _create_staff_user(db_session, username: str, password: str) -> User:
    existing = db_session.query(User).filter(User.username == username).first()
    if existing:
        return existing
    user = User(
        username=username,
        email=f"{username}@test.example",
        full_name=username.replace("_", " ").title(),
        hashed_password=get_password_hash(password),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login_headers(client, username: str, password: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/authentication/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_queue(db_session, doctor_id: int, tag: str = "procedures") -> DailyQueue:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor_id,
        queue_tag=tag,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _make_entry(
    db_session,
    queue_id: int,
    number: int,
    *,
    queue_time: datetime | None = None,
    patient_id: int | None = None,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue_id,
        number=number,
        patient_id=patient_id,
        patient_name=f"Пациент {number}",
        phone="+998900000000",
        status="waiting",
        source="desk",
        queue_time=queue_time or datetime.now(UTC) - timedelta(minutes=30),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _raw_attribution(db_session, entry_id: int):
    """ORM-bypassing column-level proof (identity-map-proof)."""
    return db_session.execute(
        text(
            "SELECT called_by_user_id, served_by_user_id, served_at "
            "FROM queue_entries WHERE id = :eid"
        ),
        {"eid": entry_id},
    ).first()


# ---------------------------------------------------------------------------
# schema / model parity
# ---------------------------------------------------------------------------


@pytest.mark.queue
@pytest.mark.integration
def test_queue_entry_attribution_columns_in_schema(db_session):
    inspector = inspect(db_session.get_bind())
    columns = {col["name"] for col in inspector.get_columns("queue_entries")}
    assert {"called_by_user_id", "served_by_user_id", "served_at"} <= columns


@pytest.mark.queue
@pytest.mark.integration
def test_attribution_columns_are_nullable_no_backfill(db_session, test_doctor):
    queue = _make_queue(db_session, test_doctor.id)
    entry = _make_entry(db_session, queue.id, number=1)

    called_by, served_by, served_at = _raw_attribution(db_session, entry.id)

    # No backfill contract: rows created without an operator stay NULL.
    assert called_by is None
    assert served_by is None
    assert served_at is None


# ---------------------------------------------------------------------------
# call-next attribution (REST)
# ---------------------------------------------------------------------------


@pytest.mark.queue
@pytest.mark.integration
def test_rest_call_next_persists_called_by_column(client, db_session, test_doctor):
    operator = _create_staff_user(db_session, "qf1_operator_a", "operator-a-pass")
    headers = _login_headers(client, "qf1_operator_a", "operator-a-pass")
    queue = _make_queue(db_session, test_doctor.id)
    entry = _make_entry(db_session, queue.id, number=1)

    resp = client.post(
        f"/api/v1/queue/{test_doctor.id}/call-next",
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    called_by, served_by, served_at = _raw_attribution(db_session, entry.id)
    assert called_by == operator.id
    assert served_by is None
    assert served_at is None


@pytest.mark.queue
@pytest.mark.integration
def test_two_operators_get_distinct_attribution(client, db_session, test_doctor):
    """The nurse-A/nurse-B scenario: two staff members, one shared queue.

    Canonical order (priority DESC, queue_time ASC, id ASC) must hand the
    EARLIEST entry to the first caller; the second caller — a different
    user — gets the NEXT waiting entry with THEIR id, never the same row
    (the FOR UPDATE guard keeps the called entry out of the waiting set).
    """
    operator_a = _create_staff_user(db_session, "qf1_operator_a", "operator-a-pass")
    operator_b = _create_staff_user(db_session, "qf1_operator_b", "operator-b-pass")
    headers_a = _login_headers(client, "qf1_operator_a", "operator-a-pass")
    headers_b = _login_headers(client, "qf1_operator_b", "operator-b-pass")

    queue = _make_queue(db_session, test_doctor.id)
    base_time = datetime.now(UTC) - timedelta(hours=2)
    earliest = _make_entry(db_session, queue.id, number=1, queue_time=base_time)
    later = _make_entry(
        db_session,
        queue.id,
        number=2,
        queue_time=base_time + timedelta(minutes=15),
    )

    resp_a = client.post(f"/api/v1/queue/{test_doctor.id}/call-next", headers=headers_a)
    resp_b = client.post(f"/api/v1/queue/{test_doctor.id}/call-next", headers=headers_b)

    assert resp_a.status_code == 200, resp_a.text
    assert resp_b.status_code == 200, resp_b.text
    assert resp_a.json()["patient"]["id"] == earliest.id
    assert resp_b.json()["patient"]["id"] == later.id

    earliest_row = _raw_attribution(db_session, earliest.id)
    later_row = _raw_attribution(db_session, later.id)
    assert earliest_row[0] == operator_a.id
    assert later_row[0] == operator_b.id
    # The first entry is still attributed to A only — B could not take it.
    assert earliest_row[0] != operator_b.id


# ---------------------------------------------------------------------------
# complete attribution (served_by / served_at)
# ---------------------------------------------------------------------------


@pytest.mark.queue
@pytest.mark.integration
def test_complete_flow_persists_served_by_and_served_at(
    client,
    db_session,
    test_doctor,
    test_patient,
    cardio_auth_headers,
    admin_auth_headers,
):
    """Real operator flow: registrar calls → doctor starts → admin completes.

    served_by must record the COMPLETER (the live human operator), not the
    routing owner (specialist_id / resource doctor).
    """
    operator_c = _create_staff_user(db_session, "qf1_operator_c", "operator-c-pass")
    headers_c = _login_headers(client, "qf1_operator_c", "operator-c-pass")

    queue = _make_queue(db_session, test_doctor.id)
    entry = _make_entry(db_session, queue.id, number=1, patient_id=test_patient.id)

    call_resp = client.post(
        f"/api/v1/queue/{test_doctor.id}/call-next",
        headers=headers_c,
    )
    assert call_resp.status_code == 200, call_resp.text
    assert call_resp.json()["patient"]["id"] == entry.id

    start_resp = client.post(
        f"/api/v1/doctor/queue/{entry.id}/start-visit",
        headers=cardio_auth_headers,
    )
    assert start_resp.status_code == 200, start_resp.text

    admin_user_id = (
        db_session.query(User).filter(User.username == "test_admin").first().id
    )
    complete_resp = client.post(
        f"/api/v1/doctor/queue/{entry.id}/complete",
        headers=admin_auth_headers,
    )
    assert complete_resp.status_code == 200, complete_resp.text
    assert complete_resp.json()["success"] is True

    called_by, served_by, served_at = _raw_attribution(db_session, entry.id)
    assert called_by == operator_c.id
    assert served_by == admin_user_id
    assert served_at is not None


# ---------------------------------------------------------------------------
# Telegram/admin staff path (service level)
# ---------------------------------------------------------------------------


@pytest.mark.queue
@pytest.mark.integration
def test_staff_call_next_patient_persists_caller(db_session, test_doctor):
    from app.services.queue_service import queue_service

    operator = _create_staff_user(db_session, "qf1_operator_d", "operator-d-pass")
    queue = _make_queue(db_session, test_doctor.id)
    entry = _make_entry(db_session, queue.id, number=1)

    result = queue_service.staff_call_next_patient(
        db_session,
        queue_id=queue.id,
        actor_user_id=operator.id,
        commit=True,
    )

    assert result["status"] == "called"
    called_by, _, _ = _raw_attribution(db_session, entry.id)
    assert called_by == operator.id


# ---------------------------------------------------------------------------
# REST/GQL audit parity
# ---------------------------------------------------------------------------


@pytest.mark.queue
@pytest.mark.integration
def test_rest_call_next_writes_critical_audit_row(client, db_session, test_doctor):
    from app.core.audit import CRITICAL_TABLES

    assert "online_queue_entries" in CRITICAL_TABLES  # GQL round-7 P1 pin

    operator = _create_staff_user(db_session, "qf1_operator_e", "operator-e-pass")
    headers = _login_headers(client, "qf1_operator_e", "operator-e-pass")
    queue = _make_queue(db_session, test_doctor.id)
    entry = _make_entry(db_session, queue.id, number=1)

    resp = client.post(f"/api/v1/queue/{test_doctor.id}/call-next", headers=headers)
    assert resp.status_code == 200, resp.text

    audit_row = (
        db_session.query(UserAuditLog)
        .filter(
            UserAuditLog.action == "CALL_NEXT",
            UserAuditLog.resource_type == "online_queue_entries",
            UserAuditLog.resource_id == entry.id,
            UserAuditLog.user_id == operator.id,
        )
        .first()
    )
    assert audit_row is not None, (
        "REST call-next must write the same row-level critical audit the "
        "GraphQL path writes (Codex round-7 P1 / round-15 parity)"
    )


# ---------------------------------------------------------------------------
# Codex QF-1 round-1 P1 closure: the REMAINING call surfaces
# (doctor-panel call route, display-board call service, legacy queue call)
# must persist the caller too — otherwise real operator actions produce
# durable NULLs despite the column existing.
# ---------------------------------------------------------------------------


@pytest.mark.queue
@pytest.mark.integration
def test_doctor_panel_call_persists_called_by(
    client, db_session, test_doctor, cardio_auth_headers
):
    queue = _make_queue(db_session, test_doctor.id)
    entry = _make_entry(db_session, queue.id, number=1)

    resp = client.post(
        f"/api/v1/doctor/queue/{entry.id}/call",
        headers=cardio_auth_headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    cardio_user_id = (
        db_session.query(User).filter(User.username == "test_cardio").first().id
    )
    called_by, _, _ = _raw_attribution(db_session, entry.id)
    assert called_by == cardio_user_id


@pytest.mark.queue
@pytest.mark.integration
def test_display_call_patient_persists_called_by(client, db_session, test_doctor):
    operator = _create_staff_user(db_session, "qf1_operator_f", "operator-f-pass")
    headers = _login_headers(client, "qf1_operator_f", "operator-f-pass")
    queue = _make_queue(db_session, test_doctor.id)
    entry = _make_entry(db_session, queue.id, number=1)

    resp = client.post(
        "/api/v1/display/call-patient",
        json={"entry_id": entry.id, "board_ids": []},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    called_by, _, _ = _raw_attribution(db_session, entry.id)
    assert called_by == operator.id


@pytest.mark.queue
@pytest.mark.integration
def test_legacy_queue_call_persists_called_by(client, db_session, test_doctor):
    operator = _create_staff_user(db_session, "qf1_operator_g", "operator-g-pass")
    headers = _login_headers(client, "qf1_operator_g", "operator-g-pass")
    queue = _make_queue(db_session, test_doctor.id)
    entry = _make_entry(db_session, queue.id, number=1)

    resp = client.post(
        f"/api/v1/queue/legacy/call/{entry.id}",
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    called_by, _, _ = _raw_attribution(db_session, entry.id)
    assert called_by == operator.id


@pytest.mark.queue
@pytest.mark.integration
def test_registrar_batch_update_called_persists_caller(
    client, db_session, test_doctor, test_patient
):
    """Codex round-2 P1: the documented PATCH batch payload
    {"action":"update","status":"called"} must attribute the operator."""
    operator = _create_staff_user(db_session, "qf1_operator_h", "operator-h-pass")
    headers = _login_headers(client, "qf1_operator_h", "operator-h-pass")
    queue = _make_queue(db_session, test_doctor.id)
    entry = _make_entry(db_session, queue.id, number=1, patient_id=test_patient.id)

    resp = client.patch(
        f"/api/v1/registrar/batch/patients/{test_patient.id}/entries/"
        f"{date.today().isoformat()}",
        json={"entries": [{"id": entry.id, "action": "update", "status": "called"}]},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    called_by, _, _ = _raw_attribution(db_session, entry.id)
    assert called_by == operator.id


# ---------------------------------------------------------------------------
# RBAC vocabulary untouched (tripwire)
# ---------------------------------------------------------------------------


@pytest.mark.queue
@pytest.mark.integration
def test_qf1_did_not_touch_rbac_vocabulary():
    from app.core.roles import Roles

    # Enum-level pin: the canonical role set on main before/after QF-1.
    assert {role.value for role in Roles} == {
        "Admin",
        "Registrar",
        "Doctor",
        "Lab",
        "Cashier",
        "cardio",
        "derma",
        "dentist",
        "Patient",
        "SuperAdmin",
    }

    qr_ops = (BACKEND_ROOT / "app/api/v1/endpoints/qr_queue/_queue_ops.py").read_text(
        encoding="utf-8"
    )
    # Both the status and the call-next routes keep the same guard.
    assert qr_ops.count(CALL_NEXT_ROLES) >= 2

    qr_helpers = (BACKEND_ROOT / "app/api/v1/endpoints/qr_queue/_helpers.py").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"QUEUE_DOCTOR_MUTATION_ROLES\s*=\s*\{(.*?)\}",
        qr_helpers,
        re.S,
    )
    assert match is not None
    members = set(re.findall(r'"([a-z_]+)"', match.group(1)))
    assert members == EXPECTED_QUEUE_MUTATION_ROLES

    doc_ops = (
        BACKEND_ROOT / "app/api/v1/endpoints/doctor_integration/_queue_ops.py"
    ).read_text(encoding="utf-8")
    complete_block = doc_ops.split(COMPLETE_ROUTE_MARK, 1)[1][:2000]
    guard_match = re.search(
        r"require_roles\((.*?)\)",
        complete_block,
        re.S,
    )
    assert guard_match is not None
    guard_roles = set(re.findall(r'"([^"]+)"', guard_match.group(1)))
    assert guard_roles == EXPECTED_COMPLETE_ROLES
