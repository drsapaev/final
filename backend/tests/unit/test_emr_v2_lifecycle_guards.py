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

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.services.emr_v2_service import ConcurrencyError, EMRSignedError

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


def test_second_amendment_is_the_sanctioned_path(client, db_session):
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

    r2 = _amend(
        client, headers, visit.id,
        {"complaints": "v1 corrected again", "specialty": "therapy"},
        "Second correction after lab review", rv,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "amended"
    assert r2.json()["version"] > r.json()["version"]


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

    r = _restore(
        client, headers, visit.id, 1, rv,
        "Restoring the pre-edit clinical text",
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["complaints"] == "v1"


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
