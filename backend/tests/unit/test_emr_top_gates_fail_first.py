"""Fail-first regressions for the top gates of audit PR #3886 (round 1, backend pair).

Findings verified against main `d1b4a5f7` (anchors byte-identical to pinned `1e7e43dc`):

- EMRCREATE-FE-001 (P1): concurrent initial EMR creation hits the unique
  `emr_records.visit_id` race; the loser rolls back, fetches the winner and
  returns it as a regular successful save — the losing clinician's payload is
  silently dropped while the UI shows SAVE_SUCCESS. Fix contract: the loser
  must raise an explicit ConcurrencyError carrying canonical conflict
  metadata (mapped to HTTP 409 by the existing save-route handler), never a
  falsely successful winner record.

- EMRTMPL-API-001 (P1/P2): `DoctorSectionTemplatesService` unconditionally
  `await`s a *synchronous* SQLAlchemy Session (the canonical `get_db`
  dependency has no async engine in this repo). Sync `Result` is not
  awaitable -> TypeError swallowed by broad handlers -> GET returns a false
  empty 200 list and sign-time template learning silently no-ops. Fix
  contract: the service performs explicit synchronous ORM calls (repo
  convention), listing no longer masks DB failures as empty success, and
  signing an EMR actually learns section templates.

All tests are synthetic: no patient data, no real PostgreSQL required for
the deterministic race injection (unique-race is modelled by raising
IntegrityError exactly at the loser's flush, matching Gate D semantics).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.api import deps
from app.db.session import get_db
from app.main import app
from app.models.emr_v2 import EMRRecord
from app.models.section_templates import DoctorSectionTemplate
from app.services.emr_v2_service import ConcurrencyError, EMRV2Service

# ---------------------------------------------------------------------------
# EMRCREATE-FE-001 — concurrent initial creation must 409, not fake success
# ---------------------------------------------------------------------------


def _winner_record(visit_id: int = 42) -> EMRRecord:
    return EMRRecord(
        id=7,
        patient_id=1,
        visit_id=visit_id,
        version=1,
        data={},
        status="in_progress",
        created_by=999,
        created_at=datetime.now(UTC),
        row_version=3,
    )


def test_emr_create_race_loser_raises_conflict_not_winner_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unique-race loser must raise ConcurrencyError with canonical metadata.

    Sequence modelled exactly as in the finding: save() observed no record,
    the winner committed first, the loser's flush raises IntegrityError, and
    after rollback get_by_visit() sees the winner. Pre-fix code returned the
    winner as a regular success — the fail-first RED state.
    """
    service = EMRV2Service()
    winner = _winner_record()

    fake_db = MagicMock()
    fake_db.add.return_value = None
    fake_db.flush.side_effect = IntegrityError(
        "INSERT INTO emr_records", {}, Exception("UNIQUE constraint failed")
    )
    fake_db.rollback.return_value = None

    # Post-rollback the loser observes the winner's record.
    monkeypatch.setattr(EMRV2Service, "get_by_visit", lambda self, db, visit_id: winner)

    with pytest.raises(ConcurrencyError) as excinfo:
        service._create_emr(
            fake_db,
            visit_id=42,
            data={"complaints": "Текст врача A"},
            user_id=1001,
            client_session_id="sess-A",
            is_draft=False,
        )

    # Canonical conflict metadata consumed by the save route's 409 handler.
    assert excinfo.value.current_version == winner.row_version == 3
    assert excinfo.value.your_version == 0  # the loser has nothing saved
    assert excinfo.value.last_edited_by == winner.created_by == 999
    assert excinfo.value.last_edited_at is not None
    # The loser's own payload must NOT be attached/persisted after rollback.
    fake_db.rollback.assert_called_once()


def test_emr_create_normal_flow_unaffected(db_session) -> None:
    """Positive control: without a race, initial creation still succeeds."""
    from app.models.patient import Patient

    patient = Patient(
        first_name="Синтетический",
        last_name="Пациент",
        sex="male",
        birth_date=datetime(1990, 1, 1).date(),
        phone="+998900000001",
    )
    db_session.add(patient)
    db_session.flush()

    from app.models.visit import Visit

    visit = Visit(
        patient_id=patient.id,
        doctor_id=1,
        visit_date=datetime.now(UTC).date(),
        visit_time="10:00",
        status="pending_confirmation",
        discount_mode="none",
        department="cardiology",
    )
    db_session.add(visit)
    db_session.flush()

    service = EMRV2Service()
    record = service.save(
        db_session,
        visit_id=visit.id,
        data={"complaints": "Синтетическая жалоба"},
        user_id=1,
        client_session_id="sess-ok",
        is_draft=True,
    )
    assert record.id is not None
    assert record.visit_id == visit.id
    assert record.row_version >= 1


# ---------------------------------------------------------------------------
# EMRTMPL-API-001 — sync Session must not be awaited; failures must not mask
# ---------------------------------------------------------------------------


@pytest.fixture()
def section_doctor(db_session):
    from app.models.user import User

    user = User(
        username=f"tmpl_doc_{uuid.uuid4().hex[:8]}",
        email=f"tmpl_{uuid.uuid4().hex[:8]}@test.com",
        full_name="Template Doctor",
        hashed_password="x",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _authorize_as(user) -> None:
    async def _current_user():
        return user

    app.dependency_overrides[deps.get_current_user] = _current_user


def _seed_template(db_session, doctor_id: int, section: str, text: str) -> None:
    db_session.add(
        DoctorSectionTemplate(
            id=str(uuid.uuid4()),
            doctor_id=doctor_id,
            section_type=section,
            template_text=text,
            template_hash=DoctorSectionTemplate.compute_hash(text),
            usage_count=1,
            is_pinned=False,
            last_used_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
        )
    )
    db_session.commit()


def test_section_templates_get_returns_seeded_template(
    client, db_session, section_doctor
) -> None:
    """GET must list the doctor's existing template (pre-fix: false-empty 200)."""
    _authorize_as(section_doctor)
    _seed_template(db_session, section_doctor.id, "complaints", "Головная боль 3 дня")

    resp = client.get("/api/v1/section-templates/complaints")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    texts = [t["template_text"] for t in body.get("templates", [])]
    assert "Головная боль 3 дня" in texts, f"false-empty list: {body}"
    assert body.get("total", 0) >= 1


def test_section_templates_db_failure_not_masked_as_empty_success(
    client, section_doctor
) -> None:
    """A broken DB session must surface as a failure, not a 200 empty list."""

    def broken_get_db():
        broken = MagicMock()
        broken.execute.side_effect = RuntimeError("synthetic db outage")
        yield broken

    app.dependency_overrides[get_db] = broken_get_db
    _authorize_as(section_doctor)

    with pytest.raises(RuntimeError):
        client.get("/api/v1/section-templates/complaints")


def test_sign_route_learns_section_templates(
    client, db_session, admin_user, test_visit
) -> None:
    """Signing an EMR must actually learn section templates (pre-fix: silent no-op)."""
    from app.services.emr_v2_service import emr_v2_service

    _authorize_as(admin_user)

    saved = emr_v2_service.save(
        db_session,
        visit_id=test_visit.id,
        data={"complaints": "Первичная жалоба"},
        user_id=admin_user.id,
        client_session_id="sess-sign",
        is_draft=True,
    )
    assert saved.status in ("draft", "in_progress")

    sign_data = {
        "complaints": "Первичная жалоба",
        "anamnesis_morbi": "Синтетический анамнез для обучения",
        "treatment": "Синтетическое лечение",
        "recommendations": "Синтетические рекомендации",
        "icd10_code": "J06.9",
    }
    resp = client.post(
        f"/api/v1/v2/emr/{test_visit.id}/sign",
        json={
            "data": sign_data,
            "row_version": saved.row_version,
            "client_session_id": "sess-sign",
        },
    )
    assert resp.status_code == 200, resp.text

    listing = client.get("/api/v1/section-templates/anamnesis")
    assert listing.status_code == 200, listing.text
    texts = [t["template_text"] for t in listing.json().get("templates", [])]
    assert "Синтетический анамнез для обучения" in texts, (
        "sign-time learning silently skipped: " + listing.text
    )
