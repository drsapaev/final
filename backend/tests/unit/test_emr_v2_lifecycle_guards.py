"""Fail-first regression suite: EMR v2 lifecycle guards (audit 3886, round 16).

Covers four ledger findings of the merged audit ledger PR #3886:

- EMRAMEND-FE-002  — finalized ("amended") records must not be editable or
  re-signable through the ordinary save/sign path; the reasoned amend flow
  is the only sanctioned repeat correction.
- EMRRESTORE-FE-001 — restore must never replace signed/amended clinical
  data outside the amendment workflow, and must require an explicit reason
  (min 10 chars) even for unsigned records.
- EMRRESTORE-FE-002 — restore honors optimistic locking (row_version);
  a stale view must fail closed with 409 instead of silently overwriting
  concurrent edits.
- EMRLOCK-FE-001 — same-session optimistic-lock bypass removed: a late
  older write with different content is a conflict; only a byte-identical
  duplicate retry is an idempotent no-op.

Red-first statement: on the pre-fix source every test below fails —
amended records were ordinary-saveable and re-signable, restore accepted
signed records without a reason and without row_version, and the
same-session bypass let a stale write overwrite a newer committed revision.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import postgresql

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.audit import AuditLog
from app.models.clinic import Doctor
from app.models.emr_v2 import EMRAuditLog, EMRRecord, EMRRevision
from app.models.enums import AppointmentStatus
from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import UserAuditLog
from app.models.visit import Visit
from app.services.emr_v2_service import (
    ConcurrencyError,
    EMRPatientContextMismatch,
    EMRSignedError,
    emr_v2_service,
)

pytestmark = pytest.mark.unit


def _mk_visit(db, label: str) -> tuple[Visit, User]:
    user = User(
        username=f"emr_life_{label}",
        email=f"emr-life-{label}@test.com",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
    )
    doctor = Doctor(user_id=user.id, specialty="therapy", active=True)
    patient = Patient(
        first_name="Lifecycle",
        last_name=label,
        phone=f"+99890966{abs(hash(label)) % 10000:04d}",
        birth_date=date(1990, 1, 1),
    )
    db.add_all([user, patient])
    db.flush()
    # user.id is only assigned after flush — link the doctor profile now
    doctor.user_id = user.id
    db.add(doctor)
    db.flush()
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        visit_time="09:00",
        status="open",
        department="therapy",
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit, user


def _login(client, username: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/authentication/login",
        json={"username": username, "password": "doctor123"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _save(client, headers, visit_id, data, row_version, session, draft=True):
    return client.post(
        f"/api/v1/v2/emr/{visit_id}",
        headers=headers,
        json={
            "data": data,
            "row_version": row_version,
            "client_session_id": session,
            "is_draft": draft,
        },
    )


def _sign(client, headers, visit_id, data, row_version, session):
    return client.post(
        f"/api/v1/v2/emr/{visit_id}/sign",
        headers=headers,
        json={
            "data": data,
            "row_version": row_version,
            "client_session_id": session,
        },
    )


def _amend(client, headers, visit_id, data, reason, row_version):
    return client.post(
        f"/api/v1/v2/emr/{visit_id}/amend",
        headers=headers,
        json={"data": data, "reason": reason, "row_version": row_version},
    )


def _restore(client, headers, visit_id, target_version, row_version, reason):
    return client.post(
        f"/api/v1/v2/emr/{visit_id}/restore",
        headers=headers,
        json={
            "target_version": target_version,
            "row_version": row_version,
            "reason": reason,
        },
    )


# ────────────────── EMRAMEND-FE-002: finalized states ──────────────────


def test_amended_emr_rejects_ordinary_save(client, db_session):
    """EMRAMEND-FE-002: after sign→amend, POST /v2/emr/{visit} must 409/400,
    not create an ordinary revision without an amendment reason."""
    visit, user = _mk_visit(db_session, "amd_save")
    headers = _login(client, user.username)
    s = "sess-amend-save"

    r = _save(client, headers, visit.id, {"complaints": "v1", "specialty": "therapy"}, 0, s)
    assert r.status_code == 200, r.text
    rv = r.json()["row_version"]
    r = _sign(client, headers, visit.id, {"complaints": "v1", "specialty": "therapy"}, rv, s)
    assert r.status_code == 200, r.text
    rv = r.json()["row_version"]
    r = _amend(
        client, headers, visit.id,
        {"complaints": "v1 corrected", "specialty": "therapy"},
        "Correction of a clerical error", rv,
    )
    assert r.status_code == 200, r.text
    amended = r.json()
    assert amended["status"] == "amended"

    # Ordinary save on the amended record must be refused
    r = _save(
        client, headers, visit.id,
        {"complaints": "unreasoned edit", "specialty": "therapy"},
        amended["row_version"], s,
    )
    assert r.status_code in (400, 409), (
        f"ordinary save must be rejected on amended record, got {r.status_code}"
    )


def test_amended_emr_rejects_resign(client, db_session):
    """EMRAMEND-FE-002: an amended record must not be re-signable via
    /sign — that would forge signature provenance."""
    visit, user = _mk_visit(db_session, "amd_sign")
    headers = _login(client, user.username)
    s = "sess-amend-sign"

    r = _save(client, headers, visit.id, {"complaints": "v1", "specialty": "therapy"}, 0, s)
    rv = r.json()["row_version"]
    r = _sign(client, headers, visit.id, {"complaints": "v1", "specialty": "therapy"}, rv, s)
    assert r.status_code == 200
    rv = r.json()["row_version"]
    r = _amend(
        client, headers, visit.id,
        {"complaints": "v1 corrected", "specialty": "therapy"},
        "Correction of a clerical error", rv,
    )
    assert r.status_code == 200
    amended = r.json()

    r = _sign(
        client, headers, visit.id,
        {"complaints": "sneaky resign", "specialty": "therapy"},
        amended["row_version"], s,
    )
    assert r.status_code in (400, 409), (
        f"re-sign must be rejected on amended record, got {r.status_code}"
    )


def test_second_amendment_is_the_sanctioned_path(client, db_session, caplog):
    """EMRAMEND-FE-002: a repeat reasoned amendment on an amended record is
    allowed and stays versioned/audited (documented repeat-amend pathway)."""
    visit, user = _mk_visit(db_session, "amd_twice")
    headers = _login(client, user.username)
    s = "sess-amend-twice"

    r = _save(client, headers, visit.id, {"complaints": "v1", "specialty": "therapy"}, 0, s)
    rv = r.json()["row_version"]
    r = _sign(client, headers, visit.id, {"complaints": "v1", "specialty": "therapy"}, rv, s)
    rv = r.json()["row_version"]
    r = _amend(
        client, headers, visit.id,
        {"complaints": "v1 corrected", "specialty": "therapy"},
        "Correction of a clerical error", rv,
    )
    assert r.status_code == 200
    rv = r.json()["row_version"]

    reason = "SYNTHETIC-AUDIT-PRIVATE-AMENDMENT"
    with caplog.at_level("INFO", logger="app.services.emr_v2_service"):
        r2 = _amend(
            client, headers, visit.id,
            {"complaints": "v1 corrected again", "specialty": "therapy"},
            reason, rv,
        )
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "amended"
    assert r2.json()["version"] > r.json()["version"]
    amended = r2.json()
    assert reason not in caplog.text
    audit = (
        db_session.query(EMRAuditLog)
        .filter_by(emr_id=amended["id"], action="amend")
        .order_by(EMRAuditLog.id.desc())
        .first()
    )
    assert audit.extra_data == {
        "version": amended["version"],
        "reason_present": True,
        "fields_changed": ["complaints"],
        "other_fields_changed": 0,
    }
    revision = client.get(
        f"/api/v1/v2/emr/{visit.id}/version/{amended['version']}", headers=headers
    )
    assert revision.status_code == 200, revision.text
    assert reason in revision.json()["change_summary"]


def test_revision_reads_audit_snapshots_and_comparison_without_clinical_values(client, db_session):
    visit, user = _mk_visit(db_session, "audit_revision")
    headers = _login(client, user.username)
    first = _save(client, headers, visit.id, {"notes": "SYNTHETIC-ORIGINAL"}, 0, "audit")
    assert first.status_code == 200, first.text
    record = first.json()
    second = _save(
        client, headers, visit.id, {"notes": "SYNTHETIC-NEWER"}, record["row_version"], "audit"
    )
    assert second.status_code == 200, second.text

    response = client.get(
        f"/api/v1/v2/emr/{visit.id}/version/{record['version']}", headers=headers
    )
    assert response.status_code == 200, response.text
    revision = response.json()
    assert revision["data"]["notes"] == "SYNTHETIC-ORIGINAL"

    old_version = record["version"]
    new_version = second.json()["version"]
    history = client.get(f"/api/v1/v2/emr/{visit.id}/history?limit=1", headers=headers)
    assert history.status_code == 200, history.text
    assert [item["version"] for item in history.json()["revisions"]] == [new_version]

    diff_url = f"/api/v1/v2/emr/{visit.id}/diff?v1={old_version}"
    diff = client.get(f"{diff_url}&v2={new_version}", headers=headers)
    assert diff.status_code == 200, diff.text
    assert "SYNTHETIC-ORIGINAL" in diff.text
    assert "SYNTHETIC-NEWER" in diff.text
    missing_diff = client.get(f"{diff_url}&v2={new_version + 1}", headers=headers)
    assert missing_diff.status_code == 400, missing_diff.text

    audit = (
        db_session.query(AuditLog)
        .filter_by(
            event_type="DOCTOR_OPEN_EMR", action="view", resource_type="emr",
            resource_id=str(record["id"]), actor_user_id=user.id,
        )
        .order_by(AuditLog.id)
        .all()
    )
    assert [entry.payload for entry in audit] == [
        {"revision_id": revision["id"], "version": old_version},
        {
            "current_version": new_version, "revision_count": 1,
            "newest_version": new_version, "oldest_version": new_version,
        },
        {"version_from": old_version, "version_to": new_version, "change_count": 1},
    ]
    assert all(entry.subject_patient_id == visit.patient_id for entry in audit)
    assert all(entry.reason_code == {"context": "visit", "id": visit.id} for entry in audit)


def test_patient_emr_list_audits_only_records_visible_to_the_doctor(client, db_session):
    visit, user = _mk_visit(db_session, "audit_patient_list")
    other_visit, other_user = _mk_visit(db_session, "audit_patient_other_owner")
    other_visit.patient_id = visit.patient_id
    db_session.commit()
    headers = _login(client, user.username)
    other_headers = _login(client, other_user.username)
    list_url = f"/api/v1/v2/emr/patient/{visit.patient_id}"
    other = _save(client, other_headers, other_visit.id, {"notes": "SYNTHETIC-PRIVATE"}, 0, "other")
    assert other.status_code == 200, other.text
    empty = client.get(list_url, headers=headers)
    assert empty.status_code == 200
    assert empty.json() == []

    saved = _save(client, headers, visit.id, {"diagnosis": "SYNTHETIC-DIAGNOSIS"}, 0, "list")
    assert saved.status_code == 200, saved.text
    visible = client.get(list_url, headers=headers)
    assert visible.status_code == 200, visible.text
    assert [entry["id"] for entry in visible.json()] == [saved.json()["id"]]
    assert visible.json()[0]["diagnosis_main"] == "SYNTHETIC-DIAGNOSIS"
    audit = db_session.query(AuditLog).filter_by(
        event_type="DOCTOR_OPEN_EMR", action="view", resource_type="emr", actor_user_id=user.id,
    ).one()
    assert audit.subject_patient_id == visit.patient_id
    assert audit.resource_id is None
    assert audit.payload == {"record_count": 1}


def test_save_audit_retains_versions_and_field_names_without_clinical_data(client, db_session):
    visit, user = _mk_visit(db_session, "audit_save")
    headers = _login(client, user.username)
    first = _save(
        client, headers, visit.id,
        {"notes": "SYNTHETIC-PREVIOUS-CONTENT", "follow_up": {"changes": "SYNTHETIC-PREVIOUS-FOLLOW-UP"}},
        0, "audit-save",
    )
    assert first.status_code == 200, first.text
    record = first.json()
    second = _save(
        client, headers, visit.id,
        {"notes": "SYNTHETIC-NEXT-CONTENT", "follow_up": {"changes": "SYNTHETIC-NEXT-FOLLOW-UP"},
         "SYNTHETIC-EXTENSION-KEY": "SYNTHETIC-EXTENSION-CONTENT"},
        record["row_version"], "audit-save",
    )
    assert second.status_code == 200, second.text
    audits = db_session.query(UserAuditLog).filter_by(
        resource_type="emr", resource_id=record["id"],
    ).order_by(UserAuditLog.id).all()
    created, edited = audits
    assert created.action == "CREATE"
    assert created.old_values is None
    assert created.new_values["version"] == record["version"]
    assert edited.action == "UPDATE"
    assert edited.old_values == {
        "version": record["version"], "row_version": record["row_version"], "status": "draft",
    }
    assert edited.new_values == {
        "version": second.json()["version"], "row_version": second.json()["row_version"],
        "status": "draft", "fields_changed": ["follow_up", "notes"], "other_fields_changed": 1,
    }
    assert "SYNTHETIC-" not in str(created.new_values)
    emr_audit = db_session.query(EMRAuditLog).filter_by(emr_id=record["id"], action="update").one()
    assert emr_audit.extra_data == {
        "version": second.json()["version"], "fields_changed": ["follow_up", "notes"], "other_fields_changed": 1,
    }


# ────────────────── EMRRESTORE-FE-001: restore policy ──────────────────


def test_restore_rejects_signed_emr(client, db_session):
    """EMRRESTORE-FE-001: restore of a signed record must be refused — old
    clinical values may not replace signed data under the original
    signature metadata."""
    visit, user = _mk_visit(db_session, "res_signed")
    headers = _login(client, user.username)
    s = "sess-restore-signed"

    r = _save(client, headers, visit.id, {"complaints": "v1", "specialty": "therapy"}, 0, s)
    rv = r.json()["row_version"]
    r = _save(client, headers, visit.id, {"complaints": "v2", "specialty": "therapy"}, rv, s)
    rv = r.json()["row_version"]
    r = _sign(client, headers, visit.id, {"complaints": "v2", "specialty": "therapy"}, rv, s)
    assert r.status_code == 200
    signed = r.json()

    r = _restore(
        client, headers, visit.id, 1, signed["row_version"],
        "Rolling back to the original text",
    )
    assert r.status_code in (400, 409), (
        f"restore must be rejected for a signed EMR, got {r.status_code}"
    )
    # data unchanged
    cur = client.get(f"/api/v1/v2/emr/{visit.id}", headers=headers).json()
    assert cur["data"]["complaints"] == "v2"


def test_restore_rejects_amended_emr(client, db_session):
    """EMRRESTORE-FE-001: amended records are finalized too — restore is
    refused, the amendment workflow is the only path."""
    visit, user = _mk_visit(db_session, "res_amend")
    headers = _login(client, user.username)
    s = "sess-restore-amend"

    r = _save(client, headers, visit.id, {"complaints": "v1", "specialty": "therapy"}, 0, s)
    rv = r.json()["row_version"]
    r = _sign(client, headers, visit.id, {"complaints": "v1", "specialty": "therapy"}, rv, s)
    rv = r.json()["row_version"]
    r = _amend(
        client, headers, visit.id,
        {"complaints": "v1 amended", "specialty": "therapy"},
        "Correction of a clerical error", rv,
    )
    assert r.status_code == 200

    r = _restore(
        client, headers, visit.id, 1, r.json()["row_version"],
        "Rolling back to the original text",
    )
    assert r.status_code in (400, 409), (
        f"restore must be rejected for an amended EMR, got {r.status_code}"
    )


def test_restore_requires_explicit_reason(client, db_session):
    """EMRRESTORE-FE-001: even for an unsigned record, a restore without a
    meaningful reason (>= 10 chars) must be rejected (schema-level)."""
    visit, user = _mk_visit(db_session, "res_reason")
    headers = _login(client, user.username)
    s = "sess-restore-reason"

    r = _save(client, headers, visit.id, {"complaints": "v1", "specialty": "therapy"}, 0, s)
    rv = r.json()["row_version"]
    r = _save(client, headers, visit.id, {"complaints": "v2", "specialty": "therapy"}, rv, s)
    rv = r.json()["row_version"]

    # Missing reason entirely
    r = client.post(
        f"/api/v1/v2/emr/{visit.id}/restore",
        headers=headers,
        json={"target_version": 1, "row_version": rv},
    )
    assert r.status_code == 422, (
        f"restore without reason must be rejected, got {r.status_code}"
    )
    # Too-short reason
    r = client.post(
        f"/api/v1/v2/emr/{visit.id}/restore",
        headers=headers,
        json={"target_version": 1, "row_version": rv, "reason": "short"},
    )
    assert r.status_code == 422, (
        f"restore with a too-short reason must be rejected, got {r.status_code}"
    )


def test_unsigned_restore_with_reason_and_version_succeeds(client, db_session):
    """EMRRESTORE-FE-001 (allowed path): a reasoned, version-matching
    restore of an unsigned record still works — regression guard for the
    new policy not breaking the legitimate flow."""
    visit, user = _mk_visit(db_session, "res_ok")
    headers = _login(client, user.username)
    s = "sess-restore-ok"

    r = _save(client, headers, visit.id, {"complaints": "v1", "specialty": "therapy"}, 0, s)
    assert r.status_code == 200
    rv = r.json()["row_version"]
    r = _save(client, headers, visit.id, {"complaints": "v2", "specialty": "therapy"}, rv, s)
    assert r.status_code == 200
    rv = r.json()["row_version"]

    reason = "SYNTHETIC-AUDIT-PRIVATE-RESTORE"
    r = _restore(client, headers, visit.id, 1, rv, reason)
    assert r.status_code == 200, r.text
    restored = r.json()
    assert restored["data"]["complaints"] == "v1"
    audit = db_session.query(EMRAuditLog).filter_by(emr_id=restored["id"], action="restore").one()
    assert audit.extra_data == {
        "from_version": 1, "to_version": restored["version"], "reason_present": True,
    }
    revision = client.get(
        f"/api/v1/v2/emr/{visit.id}/version/{restored['version']}", headers=headers
    )
    assert revision.status_code == 200, revision.text
    assert reason in revision.json()["change_summary"]


# ────────────────── EMRRESTORE-FE-002: optimistic locking ──────────────────


def test_stale_restore_returns_409(client, db_session):
    """EMRRESTORE-FE-002: another user committed N+1 while our view holds
    N — the stale restore must fail closed instead of overwriting."""
    visit, user = _mk_visit(db_session, "res_stale")
    headers = _login(client, user.username)
    s = "sess-restore-stale"

    r = _save(client, headers, visit.id, {"complaints": "v1", "specialty": "therapy"}, 0, s)
    stale_view = r.json()["row_version"]
    r = _save(client, headers, visit.id, {"complaints": "v2", "specialty": "therapy"}, stale_view, s)
    assert r.status_code == 200
    current = r.json()["row_version"]
    assert current > stale_view

    r = _restore(
        client, headers, visit.id, 1, stale_view,
        "Stale view restore must conflict",
    )
    assert r.status_code == 409, (
        f"stale restore must 409, got {r.status_code}"
    )
    cur = client.get(f"/api/v1/v2/emr/{visit.id}", headers=headers).json()
    assert cur["data"]["complaints"] == "v2"
    assert cur["row_version"] == current


# ────────────────── EMRLOCK-FE-001: same-session ordering ──────────────────


def test_same_session_stale_write_fails_closed(client, db_session):
    """EMRLOCK-FE-001: two same-session requests share row_version N; the
    newer content commits first, the late older write must 409 — the
    same-session bypass must not resurrect stale clinical text."""
    visit, user = _mk_visit(db_session, "lock_stale")
    headers = _login(client, user.username)
    s = "sess-lock-stale"

    r = _save(client, headers, visit.id, {"complaints": "base", "specialty": "therapy"}, 0, s)
    assert r.status_code == 200
    n = r.json()["row_version"]

    # B (newer text) commits first with version N
    r_b = _save(client, headers, visit.id, {"complaints": "newer text B", "specialty": "therapy"}, n, s)
    assert r_b.status_code == 200, r_b.text

    # A (older text) arrives late with the same stale version N — must 409
    r_a = _save(client, headers, visit.id, {"complaints": "older text A", "specialty": "therapy"}, n, s)
    assert r_a.status_code == 409, (
        f"same-session stale write must 409, got {r_a.status_code}"
    )

    cur = client.get(f"/api/v1/v2/emr/{visit.id}", headers=headers).json()
    assert cur["data"]["complaints"] == "newer text B", (
        "the newer committed revision must remain authoritative"
    )


def test_same_session_identical_retry_is_idempotent_noop(client, db_session):
    """EMRLOCK-FE-001 (allowed path): a byte-identical duplicate retry from
    the same session is an idempotent no-op — no extra revision, no version
    bump, current content preserved."""
    visit, user = _mk_visit(db_session, "lock_dup")
    headers = _login(client, user.username)
    s = "sess-lock-dup"

    r = _save(client, headers, visit.id, {"complaints": "stable text", "specialty": "therapy"}, 0, s)
    assert r.status_code == 200
    first = r.json()

    # exact duplicate retry with the now-stale version
    r2 = _save(client, headers, visit.id, {"complaints": "stable text", "specialty": "therapy"}, 0, s)
    assert r2.status_code == 200, r2.text
    second = r2.json()
    assert second["row_version"] == first["row_version"], (
        "identical duplicate retry must not bump row_version"
    )
    assert second["version"] == first["version"], (
        "identical duplicate retry must not create a new revision"
    )


def test_same_session_stale_version_cannot_sign_or_promote_matching_draft(client, db_session):
    visit, user = _mk_visit(db_session, "stale_sign")
    headers = _login(client, user.username)
    session = "same-session-sign-order"
    initial = _save(client, headers, visit.id, {"notes": "SYNTHETIC-INITIAL"}, 0, session)
    assert initial.status_code == 200, initial.text
    stale_version = initial.json()["row_version"]
    data = {"notes": "SYNTHETIC-UPDATED"}
    current = _save(client, headers, visit.id, data, stale_version, session)
    assert current.status_code == 200, current.text

    sign = _sign(client, headers, visit.id, data, stale_version, session)
    assert sign.status_code == 409, sign.text
    assert sign.json()["detail"]["error"] == "CONFLICT"
    finalize = _save(client, headers, visit.id, data, stale_version, session, draft=False)
    assert finalize.status_code == 409, finalize.text
    saved = client.get(f"/api/v1/v2/emr/{visit.id}", headers=headers).json()
    assert saved["row_version"] == current.json()["row_version"]
    assert saved["status"] == "draft"
    assert saved["signed_at"] is None


def test_emr_lifecycle_writes_lock_visit_before_record(db_session):
    visit, user = _mk_visit(db_session, "write_lock")
    locking_reads = []
    dialect = postgresql.dialect()

    @event.listens_for(db_session, "do_orm_execute")
    def capture_lock(execution):
        if execution.is_select:
            statement = str(execution.statement.compile(dialect=dialect))
            if "FOR UPDATE" in statement:
                locking_reads.append(statement.split("FROM ", 1)[1].split()[0])

    data = {"notes": "SYNTHETIC-NOTE"}
    emr = emr_v2_service.save(db_session, visit.id, data, user.id)
    emr = emr_v2_service.save(db_session, visit.id, data, user.id, emr.row_version)
    emr = emr_v2_service.restore(
        db_session, visit.id, target_version=1, user_id=user.id,
        row_version=emr.row_version, reason="SYNTHETIC revision restore",
    )
    emr = emr_v2_service.sign(db_session, visit.id, data, user.id, emr.row_version)
    emr_v2_service.amend(
        db_session, visit.id, data, "SYNTHETIC amendment", user.id, emr.row_version
    )
    emr_v2_service.get_by_visit(db_session, visit.id)

    assert locking_reads == ["visits", "emr_records"] * 5


@pytest.mark.parametrize("operation", ("save", "mobile_save", "sign", "amend", "restore"))
def test_emr_write_checks_current_visit_owner(client, db_session, operation):
    visit, user = _mk_visit(db_session, f"reassigned_{operation}")
    visit_id = visit.id
    headers = _login(client, user.username)
    initial = {"notes": "SYNTHETIC-ORIGINAL"}
    saved = _save(client, headers, visit_id, initial, 0, "reassignment")
    assert saved.status_code == 200, saved.text
    if operation == "amend":
        saved = _sign(client, headers, visit_id, initial, saved.json()["row_version"], "reassignment")
        assert saved.status_code == 200, saved.text
    row_version = saved.json()["row_version"]

    db_session.refresh(visit)
    db_session.execute(Visit.__table__.update().where(Visit.id == visit_id).values(doctor_id=None))
    assert visit.doctor_id is not None

    url = f"/api/v1/v2/emr/{visit_id}"
    payload = {"data": {"notes": "SYNTHETIC-EDIT"}, "row_version": row_version}
    if operation == "mobile_save":
        url = f"/api/v1/emr/{visit_id}"
    elif operation != "save":
        url += f"/{operation}"
    if operation in {"amend", "restore"}:
        payload["reason"] = "SYNTHETIC reason for correction"
    if operation == "restore":
        payload = {"target_version": 1, "row_version": row_version, "reason": payload["reason"]}

    response = client.post(url, headers=headers, json=payload)
    assert response.status_code == 403, response.text
    current = emr_v2_service.get_by_visit(db_session, visit_id)
    assert current.row_version == row_version
    assert current.data["notes"] == initial["notes"]


def test_inactive_emr_account_cannot_use_canonical_or_mobile_route(client, db_session):
    visit, user = _mk_visit(db_session, "inactive_account")
    visit_id = visit.id
    headers = _login(client, user.username)
    payload = {"data": {"notes": "SYNTHETIC-ORIGINAL"}, "row_version": 0}
    saved = client.post(f"/api/v1/v2/emr/{visit_id}", headers=headers, json=payload)
    assert saved.status_code == 200, saved.text
    payload["row_version"] = saved.json()["row_version"]
    payload["data"]["notes"] = "SYNTHETIC-EDIT"

    user.is_active = False
    db_session.commit()
    for prefix in ("/api/v1/v2/emr", "/api/v1/emr"):
        url = f"{prefix}/{visit_id}"
        assert client.get(url, headers=headers).status_code == 403
        assert client.post(url, headers=headers, json=payload).status_code == 403

    current = emr_v2_service.get_by_visit(db_session, visit_id)
    assert current.row_version == saved.json()["row_version"]
    assert current.data["notes"] == "SYNTHETIC-ORIGINAL"


def test_inconsistent_stored_patient_context_denies_chart_reads_and_writes(client, db_session):
    visit, user = _mk_visit(db_session, "context_guard")
    unrelated_visit, _ = _mk_visit(db_session, "context_guard_other")
    visit_id, original_patient_id = visit.id, visit.patient_id
    current_patient_id = unrelated_visit.patient_id
    appointment = Appointment(
        patient_id=original_patient_id, doctor_id=visit.doctor_id,
        appointment_date=visit.visit_date, appointment_time=visit.visit_time,
        status=AppointmentStatus.IN_VISIT,
    )
    db_session.add(appointment)
    db_session.commit()
    appointment_id = appointment.id
    headers = _login(client, user.username)
    route = f"/api/v1/v2/emr/{visit_id}"
    assert client.get(route, headers=headers).status_code == 404
    saved = _save(client, headers, visit_id, {"notes": "SYNTHETIC-DRAFT"}, 0, "context")
    assert saved.status_code == 200, saved.text
    updated = _save(
        client, headers, visit_id, {"complaints": "SYNTHETIC-CURRENT", "specialty": "general"},
        saved.json()["row_version"], "context", draft=False,
    )
    assert updated.status_code == 200, updated.text
    snapshot = updated.json()
    record_id = snapshot["id"]
    mobile_route = f"/api/v1/emr/{visit_id}"
    read_routes = (
        route, mobile_route, f"{route}/history", f"{route}/version/2", f"{route}/diff?v1=1&v2=2",
        f"/api/v1/appointments/{appointment_id}/emr",
    )
    for read_route in read_routes:
        result = client.get(read_route, headers=headers)
        assert result.status_code == 200, result.text
    suggestions_route = "/api/v1/v2/emr/doctor-history"
    suggestions = {"doctor_id": user.id, "field_name": "complaints", "specialty": "general"}
    assert client.get(suggestions_route, params=suggestions, headers=headers).json()["total"] == 1

    def audit_counts():
        return (
            db_session.query(EMRAuditLog).filter_by(emr_id=record_id).count(),
            db_session.query(AuditLog).filter_by(event_type="DOCTOR_OPEN_EMR").count(),
            db_session.query(UserAuditLog).count(),
        )

    before_audit = audit_counts()
    # Introduce an inconsistent stored pair while leaving the ORM's Visit cached.
    db_session.refresh(visit)
    db_session.execute(
        Visit.__table__.update().where(Visit.id == visit_id).values(patient_id=current_patient_id)
    )
    db_session.execute(
        Appointment.__table__.update()
        .where(Appointment.id == appointment_id).values(patient_id=current_patient_id)
    )
    db_session.expire(appointment)
    assert visit.patient_id == original_patient_id

    for read_route in read_routes:
        denied = client.get(read_route, headers=headers)
        assert denied.status_code == 409, denied.text
        assert denied.json() == {"detail": {"code": "PATIENT_CONTEXT_CHANGED"}}
    for patient_id in (original_patient_id, current_patient_id):
        listed = client.get(f"/api/v1/v2/emr/patient/{patient_id}", headers=headers)
        assert listed.status_code == 200, listed.text
        assert listed.json() == []
    assert client.get(suggestions_route, params=suggestions, headers=headers).json()["total"] == 0

    payload = {
        "data": snapshot["data"], "row_version": snapshot["row_version"],
        "client_session_id": "context",
    }
    for write_route in (route, mobile_route, f"{route}/sign", f"{route}/amend", f"{route}/restore"):
        body = dict(payload)
        if write_route.endswith("/amend"):
            body["reason"] = "SYNTHETIC amendment reason"
        if write_route.endswith("/restore"):
            body = {
                "target_version": 1, "row_version": snapshot["row_version"],
                "reason": "SYNTHETIC restore reason",
            }
        denied = client.post(write_route, headers=headers, json=body)
        assert denied.status_code == 409, denied.text
        assert denied.json() == {"detail": {"code": "PATIENT_CONTEXT_CHANGED"}}

    with pytest.raises(EMRPatientContextMismatch):
        emr_v2_service.save(db_session, visit_id, snapshot["data"], user.id, row_version=0)
    record = db_session.query(EMRRecord).filter_by(visit_id=visit_id).one()
    assert record.patient_id == original_patient_id
    assert record.row_version == snapshot["row_version"]
    assert record.data == snapshot["data"]
    assert record.signed_at is None
    assert db_session.query(EMRRevision).filter_by(emr_id=record_id).count() == 2
    assert audit_counts() == before_audit


def test_first_save_requires_the_selected_patient_when_supplied(client, db_session):
    visit, user = _mk_visit(db_session, "first_save_context")
    destination, _ = _mk_visit(db_session, "first_save_context_other")
    visit_id, selected_patient_id = visit.id, visit.patient_id
    current_patient_id = destination.patient_id
    headers = _login(client, user.username)
    db_session.execute(
        Visit.__table__.update().where(Visit.id == visit_id).values(patient_id=current_patient_id)
    )

    route = f"/api/v1/v2/emr/{visit_id}"
    payload = {"data": {"notes": "SYNTHETIC-DRAFT"}, "expected_patient_id": selected_patient_id}
    denied = client.post(route, headers=headers, json=payload)
    assert denied.status_code == 409, denied.text
    assert denied.json() == {"detail": {"code": "PATIENT_CONTEXT_CHANGED"}}
    assert db_session.query(EMRRecord).filter_by(visit_id=visit_id).count() == 0
    assert db_session.query(EMRAuditLog).filter_by(visit_id=visit_id).count() == 0

    confirmed = client.post(route, headers=headers, json={**payload, "expected_patient_id": current_patient_id})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["patient_id"] == current_patient_id


def test_cross_session_stale_write_still_conflicts(client, db_session):
    """EMRLOCK-FE-001 control: cross-session stale writes were already
    rejected; they must stay rejected (regression guard)."""
    visit, user = _mk_visit(db_session, "lock_cross")
    headers = _login(client, user.username)
    s1 = "sess-lock-cross-1"

    r = _save(client, headers, visit.id, {"complaints": "base", "specialty": "therapy"}, 0, s1)
    n = r.json()["row_version"]
    r = _save(client, headers, visit.id, {"complaints": "mine", "specialty": "therapy"}, n, s1)
    assert r.status_code == 200

    # Different session, stale version, different content
    r2 = _save(client, headers, visit.id, {"complaints": "other session", "specialty": "therapy"}, n, "sess-lock-cross-2")
    assert r2.status_code == 409


def test_service_level_amended_guard(db_session):
    """EMRAMEND-FE-002 (service level, no HTTP): _update_emr rejects the
    amended state directly; amend() is the sanctioned path."""
    from app.services.emr_v2_service import emr_v2_service

    visit, user = _mk_visit(db_session, "svc_amend")
    emr = emr_v2_service.save(
        db_session, visit.id, {"complaints": "v1", "specialty": "therapy"}, user.id
    )
    emr = emr_v2_service.sign(
        db_session, visit.id, {"complaints": "v1", "specialty": "therapy"}, user.id, emr.row_version
    )
    emr = emr_v2_service.amend(
        db_session, visit.id,
        {"complaints": "v1 corrected", "specialty": "therapy"},
        "Correction of a clerical error", user.id, emr.row_version,
    )
    assert emr.status == "amended"

    with pytest.raises(EMRSignedError):
        emr_v2_service.save(
            db_session, visit.id,
            {"complaints": "unreasoned", "specialty": "therapy"},
            user.id, row_version=emr.row_version,
        )

    with pytest.raises(EMRSignedError):
        emr_v2_service.sign(
            db_session, visit.id,
            {"complaints": "unreasoned resign", "specialty": "therapy"},
            user.id, emr.row_version,
        )

    with pytest.raises(EMRSignedError):
        emr_v2_service.restore(
            db_session, visit.id, 1, user.id,
            row_version=emr.row_version, reason="Rolling back the amendment",
        )


def test_service_level_stale_same_session_write(db_session):
    """EMRLOCK-FE-001 (service level): on a DRAFT record (no finalized-state
    guard in the way) a stale same-session write with different content
    raises ConcurrencyError; an identical retry is a no-op."""
    from app.services.emr_v2_service import emr_v2_service

    visit, user = _mk_visit(db_session, "svc_stale")
    emr = emr_v2_service.save(
        db_session, visit.id, {"complaints": "draft text", "specialty": "therapy"},
        user.id, client_session_id="svc-session",
    )
    assert emr.row_version == 1

    # Identical duplicate retry with stale version -> idempotent no-op
    same = emr_v2_service.save(
        db_session, visit.id, {"complaints": "draft text", "specialty": "therapy"},
        user.id, row_version=0, client_session_id="svc-session",
    )
    assert same.row_version == 1 and same.version == emr.version

    # Stale version with DIFFERENT content -> fail closed
    with pytest.raises(ConcurrencyError):
        emr_v2_service.save(
            db_session, visit.id,
            {"complaints": "stale older write", "specialty": "therapy"},
            user.id, row_version=0, client_session_id="svc-session",
        )
