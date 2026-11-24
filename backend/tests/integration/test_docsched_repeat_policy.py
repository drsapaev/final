"""Repeat-visit eligibility, clinic configuration and exact prices."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_UP, Decimal, Inexact, Rounded, localcontext

import pytest

from app.models.clinic import ClinicSettings, Doctor
from app.models.visit import Visit, VisitService
from app.models.visit_invitation_delivery import VisitInvitationDelivery
from app.services.doctor_repeat_discount import (
    RepeatDiscountSnapshot,
    RepeatPolicyError,
    prepare_repeat_discount,
)
from tests.integration.doctor_schedule_fixtures import (
    mock_invitations as mock_invitations,
)
from tests.integration.test_docsched_schedule_next_integrity import (
    _clinic_today,
    _make_patient,
    _make_service,
    _pending_visits,
    _schedule_payload,
)

TODAY = date(2026, 11, 17)
TARGET = TODAY + timedelta(days=4)


def _setting(db, key, value):
    row = db.query(ClinicSettings).filter(ClinicSettings.key == key).first()
    if row is None:
        row = ClinicSettings(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()


def _prior(db, patient, doctor, service, when, status="completed"):
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=when,
        status=status,
        discount_mode="none",
        source="desk",
        repeat_evidence_generation=1,
        repeat_proof_generation=1,
        repeat_proof_consultation=bool(service.is_consultation),
        repeat_proof_doctor_user_id=doctor.user_id,
    )
    db.add(visit)
    db.flush()
    db.add(VisitService(visit_id=visit.id, service_id=service.id, name=service.name, qty=1, price=service.price))
    db.commit()
    return visit


def _snapshot(db, patient, doctor_id, *, target=TARGET, today=TODAY):
    doctor = db.get(Doctor, doctor_id) if doctor_id is not None else None
    return prepare_repeat_discount(
        db, patient_id=patient.id, doctor_id=doctor_id,
        doctor_user_id=doctor.user_id if doctor is not None else None,
        target_date=target, clinic_today=today,
    )


def _eligible(db, snapshot, requested, historical):
    services = {s.id: s for s in (*requested, *historical)}
    snapshot.require_eligible(db, services, [s.id for s in requested])


@pytest.mark.parametrize("status", ["completed", "closed"])
def test_completed_consultation_uses_configured_discount_and_keeps_other_prices(
    db_session, test_doctor, status
):
    patient = _make_patient(db_session)
    previous = _make_service(db_session, price=Decimal("200.00"), is_consultation=True)
    previous.active = False  # Historic classification remains valid after withdrawal.
    requested = _make_service(db_session, price=Decimal("123.45"), is_consultation=True)
    other = _make_service(db_session, price=Decimal("3.99"), is_consultation=False)
    db_session.commit()
    _prior(db_session, patient, test_doctor, previous, TODAY - timedelta(days=2), status)
    _setting(db_session, "repeat_visit_discount", 20)
    snapshot = _snapshot(db_session, patient, test_doctor.id)
    _eligible(db_session, snapshot, [requested, other], [previous])
    assert snapshot.percentage == Decimal("20")
    assert snapshot.price(Decimal("123.45"), True) == Decimal("98.76")
    assert snapshot.price(Decimal("3.99"), False) == Decimal("3.99")
    assert snapshot.historical_service_ids == ()


@pytest.mark.parametrize("status", ["open", "confirmed", "in_progress", "pending_confirmation", "cancelled", "canceled", "expired"])
def test_unfinished_cancelled_or_expired_visit_is_not_prior_consultation(
    db_session, test_doctor, status
):
    patient = _make_patient(db_session)
    service = _make_service(db_session, is_consultation=True)
    _prior(db_session, patient, test_doctor, service, TODAY - timedelta(days=1), status)
    snapshot = _snapshot(db_session, patient, test_doctor.id)
    with pytest.raises(RepeatPolicyError):
        _eligible(db_session, snapshot, [service], [service])


@pytest.mark.parametrize("prior_delta,allowed", [(21, True), (22, False), (-1, False)])
def test_window_is_relative_to_target_and_rejects_future_completed_visits(
    db_session, test_doctor, prior_delta, allowed
):
    patient = _make_patient(db_session)
    service = _make_service(db_session, is_consultation=True)
    # Delta -1 means a completed-in-name-only future appointment after today.
    _prior(db_session, patient, test_doctor, service, TARGET - timedelta(days=prior_delta))
    snapshot = _snapshot(db_session, patient, test_doctor.id)
    if allowed:
        _eligible(db_session, snapshot, [service], [service])
    else:
        with pytest.raises(RepeatPolicyError):
            _eligible(db_session, snapshot, [service], [service])


def test_unrelated_patient_or_doctor_cannot_use_previous_consultation(db_session, test_doctor):
    patient, other = _make_patient(db_session), _make_patient(db_session)
    service = _make_service(db_session, is_consultation=True)
    _prior(db_session, patient, test_doctor, service, TODAY - timedelta(days=1))
    snapshot = _snapshot(db_session, other, test_doctor.id)
    with pytest.raises(RepeatPolicyError):
        _eligible(db_session, snapshot, [service], [service])
    with pytest.raises(RepeatPolicyError):
        _snapshot(db_session, patient, test_doctor.id + 1000)
    with pytest.raises(RepeatPolicyError):
        _snapshot(db_session, patient, None)


@pytest.mark.parametrize("prior_consultation,requested_consultation", [(False, True), (True, False), (False, False)])
def test_both_prior_and_new_services_must_include_consultation(
    db_session, test_doctor, prior_consultation, requested_consultation
):
    patient = _make_patient(db_session)
    prior = _make_service(db_session, is_consultation=prior_consultation)
    requested = _make_service(db_session, is_consultation=requested_consultation)
    _prior(db_session, patient, test_doctor, prior, TODAY - timedelta(days=1))
    snapshot = _snapshot(db_session, patient, test_doctor.id)
    with pytest.raises(RepeatPolicyError):
        _eligible(db_session, snapshot, [requested], [prior])


def test_historical_catalog_reclassification_does_not_rewrite_evidence(db_session, test_doctor):
    patient = _make_patient(db_session)
    prior = _make_service(db_session, is_consultation=True)
    requested = _make_service(db_session, is_consultation=True)
    _prior(db_session, patient, test_doctor, prior, TODAY - timedelta(days=1))
    snapshot = _snapshot(db_session, patient, test_doctor.id)
    # Current catalog classification cannot erase the completion-time proof.
    prior.is_consultation = False
    _eligible(db_session, snapshot, [requested], [prior])


@pytest.mark.parametrize("case", ["legacy", "stale", "not_consultation", "different_owner"])
def test_missing_stale_or_mismatched_completion_proof_cannot_authorize_repeat(
    db_session, test_doctor, case
):
    patient = _make_patient(db_session)
    service = _make_service(db_session, is_consultation=True)
    prior = _prior(db_session, patient, test_doctor, service, TODAY - timedelta(days=1))
    if case == "legacy":
        prior.repeat_proof_generation = None
        prior.repeat_proof_consultation = None
        prior.repeat_proof_doctor_user_id = None
    elif case == "stale":
        prior.repeat_evidence_generation += 1
    elif case == "not_consultation":
        prior.repeat_proof_consultation = False
    else:
        prior.repeat_proof_doctor_user_id = test_doctor.user_id + 1000
    db_session.commit()
    snapshot = _snapshot(db_session, patient, test_doctor.id)
    with pytest.raises(RepeatPolicyError):
        _eligible(db_session, snapshot, [service], [service])


def test_missing_requested_catalog_row_fails_closed(db_session, test_doctor):
    patient = _make_patient(db_session)
    service = _make_service(db_session, is_consultation=True)
    _prior(db_session, patient, test_doctor, service, TODAY - timedelta(days=1))
    snapshot = _snapshot(db_session, patient, test_doctor.id)
    with pytest.raises(RepeatPolicyError):
        snapshot.require_eligible(db_session, {service.id: service}, [service.id, service.id + 1000])


@pytest.mark.parametrize("days", [0, 366, -1, True, None, "1.5", "NaN"])
def test_invalid_window_configuration_fails_closed(db_session, test_doctor, days):
    patient = _make_patient(db_session)
    _setting(db_session, "repeat_visit_days", days)
    with pytest.raises(RepeatPolicyError):
        _snapshot(db_session, patient, test_doctor.id)


@pytest.mark.parametrize("percentage", [-1, 101, True, None, "1.5", "Infinity"])
def test_invalid_percentage_configuration_fails_closed(db_session, test_doctor, percentage):
    patient = _make_patient(db_session)
    _setting(db_session, "repeat_visit_discount", percentage)
    with pytest.raises(RepeatPolicyError):
        _snapshot(db_session, patient, test_doctor.id)


@pytest.mark.parametrize("percentage,expected", [(0, "0.05"), (10, "0.04"), (100, "0.00")])
def test_valid_percentage_bounds_and_registrar_decimal_rounding(db_session, test_doctor, percentage, expected):
    patient = _make_patient(db_session)
    _setting(db_session, "repeat_visit_discount", percentage)
    snapshot = _snapshot(db_session, patient, test_doctor.id)
    assert snapshot.price(Decimal("0.05"), True) == Decimal(expected)


@pytest.mark.parametrize("rounding", [ROUND_UP, ROUND_DOWN])
@pytest.mark.parametrize("price,percentage,expected", [
    ("123.45", "10", "111.10"),
    ("0.05", "10", "0.04"),
    ("0.15", "10", "0.14"),
    ("9999999999.99", "1", "9899999999.99"),
    ("9999999999.99", "100", "0.00"),
])
def test_repeat_price_is_independent_of_caller_decimal_context(rounding, price, percentage, expected):
    snapshot = RepeatDiscountSnapshot(Decimal(percentage), (1,), ())
    with localcontext() as context:
        context.prec = 1
        context.rounding = rounding
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        assert snapshot.price(Decimal(price), True) == Decimal(expected)
        assert context.prec == 1 and context.rounding == rounding
        assert context.traps[Inexact] and context.traps[Rounded]
        assert snapshot.price(Decimal(price), False) == Decimal(price)


def test_defaults_and_valid_window_bounds(db_session, test_doctor):
    patient = _make_patient(db_session)
    default = _snapshot(db_session, patient, test_doctor.id)
    assert default.percentage == Decimal("0")
    assert default.price(Decimal("123.45"), True) == Decimal("123.45")
    db_session.rollback()
    for days in (1, 365):
        _setting(db_session, "repeat_visit_days", days)
        assert _snapshot(db_session, patient, test_doctor.id).percentage == Decimal("0")
        db_session.rollback()


def test_http_repeat_applies_configured_percentage_and_offers_correct_total(
    client, db_session, cardio_auth_headers, test_doctor, mock_invitations
):
    patient = _make_patient(db_session)
    previous = _make_service(db_session, price=Decimal("30.00"), is_consultation=True)
    requested = _make_service(db_session, price=Decimal("123.45"), is_consultation=True)
    today = _clinic_today(db_session)
    _prior(db_session, patient, test_doctor, previous, today - timedelta(days=2))
    _setting(db_session, "repeat_visit_discount", 20)
    payload = _schedule_payload(patient, requested, visit_date=today + timedelta(days=1), discount_mode="repeat")
    response = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=cardio_auth_headers)
    assert response.status_code == 200, response.text
    visit_id = response.json()["visit_id"]
    line = db_session.query(VisitService).filter(VisitService.visit_id == visit_id).one()
    assert line.price == Decimal("98.76")
    assert Decimal(str(response.json()["confirmation"]["total_amount"])) == Decimal("98.76")
    assert mock_invitations == []
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id, state="pending").count() == 1


@pytest.mark.parametrize("prior_offset,prior_status,target_offset", [(-1, "open", 1), (1, "completed", 5), (-2, "completed", 30)])
def test_http_repeat_rejects_ineligible_prior_without_visit_or_invitation(
    client, db_session, cardio_auth_headers, test_doctor, mock_invitations,
    prior_offset, prior_status, target_offset,
):
    patient = _make_patient(db_session)
    previous = _make_service(db_session, is_consultation=True)
    requested = _make_service(db_session, is_consultation=True)
    today = _clinic_today(db_session)
    _prior(db_session, patient, test_doctor, previous, today + timedelta(days=prior_offset), prior_status)
    _setting(db_session, "repeat_visit_days", 10)
    payload = _schedule_payload(patient, requested, visit_date=today + timedelta(days=target_offset), discount_mode="repeat")
    response = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=cardio_auth_headers)
    assert response.status_code == 409, response.text
    assert _pending_visits(db_session, patient_id=patient.id) == []
    assert mock_invitations == []
