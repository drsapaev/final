"""Catalog eligibility and exact-money regressions for doctor visit services.

HTTP calls use synthetic records and the invitation transport is mocked.
A rejected request must not create any part of a visit or service line.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.visit import VisitService
from tests.integration.doctor_schedule_fixtures import (
    keyed_schedule_headers,
    mock_invitations,  # noqa: F401
    observe_invitation_staging,
)
from tests.integration.test_docsched_schedule_next_integrity import (
    _clinic_today,
    _make_patient,
    _make_service,
    _pending_visits,
    _prior_context_visit,
    _schedule_payload,
)

pytestmark = pytest.mark.usefixtures("mock_invitations")


@pytest.fixture
def invitation_calls(monkeypatch):
    return observe_invitation_staging(monkeypatch)


@pytest.fixture
def patient_visit(db_session, test_doctor, invitation_calls):
    patient = _make_patient(db_session)
    visit = _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
    return patient, visit


def _schedule(client, headers, db, patient, service, *, custom_price=None, quantity=1, **extra):
    item = {"service_id": service.id, "quantity": quantity}
    if custom_price is not None:
        item["custom_price"] = custom_price
    services = extra.pop("services", [item])
    payload = _schedule_payload(
        patient,
        service,
        visit_date=_clinic_today(db) + timedelta(days=1),
        services=services,
        **extra,
    )
    return client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)


def _add(client, headers, visit_id, service_id, *, custom_price=None, quantity=1):
    params = {"service_id": service_id, "quantity": quantity}
    if custom_price is not None:
        params["custom_price"] = custom_price
    return client.put(
        f"/api/v1/doctor/visits/{visit_id}/add-service",
        params=params,
        headers=headers,
    )


def _service_rows(db, visit_id):
    db.expire_all()
    return db.query(VisitService).filter(VisitService.visit_id == visit_id).all()


def test_inactive_service_blocks_new_schedule_atomically(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls
):
    patient, _ = patient_visit
    active = _make_service(db_session, price=Decimal("100.00"))
    inactive = _make_service(db_session, price=Decimal("200.00"))
    inactive.active = False
    db_session.commit()
    response = _schedule(
        client,
        cardio_auth_headers,
        db_session,
        patient,
        active,
        services=[
            {"service_id": active.id, "quantity": 1},
            {"service_id": inactive.id, "quantity": 1},
        ],
    )
    assert response.status_code == 400, response.text
    assert _pending_visits(db_session, patient_id=patient.id) == []
    assert invitation_calls == []


def test_inactive_service_blocks_add_but_historical_visit_remains_readable(
    client, db_session, cardio_auth_headers, patient_visit
):
    _, visit = patient_visit
    inactive = _make_service(db_session, price=Decimal("123.45"))
    line = VisitService(
        visit_id=visit.id,
        service_id=inactive.id,
        code=inactive.code,
        name=inactive.name,
        qty=1,
        price=Decimal("123.45"),
        currency="UZS",
        created_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(line)
    inactive.active = False
    db_session.commit()
    before_ids = {row.id for row in _service_rows(db_session, visit.id)}

    denied = _add(client, cardio_auth_headers, visit.id, inactive.id)
    assert denied.status_code == 400, denied.text
    assert {row.id for row in _service_rows(db_session, visit.id)} == before_ids

    historical = client.get(f"/api/v1/doctor/visits/{visit.id}", headers=cardio_auth_headers)
    assert historical.status_code == 200, historical.text
    lines = historical.json()["visit"]["services"]
    assert any(item["service_id"] == inactive.id and Decimal(str(item["price"])) == Decimal("123.45") for item in lines)


def test_add_service_requires_catalogue_override_flag(
    client, db_session, cardio_auth_headers, patient_visit,
):
    _, visit = patient_visit
    service = _make_service(db_session, price=Decimal("100.00"))
    denied = _add(client, cardio_auth_headers, visit.id, service.id, custom_price="90.00")
    assert denied.status_code == 422, denied.text
    assert _service_rows(db_session, visit.id) == []

    service.allow_doctor_price_override = True
    db_session.commit()
    allowed = _add(client, cardio_auth_headers, visit.id, service.id, custom_price="90.00")
    assert allowed.status_code == 200, allowed.text
    assert _service_rows(db_session, visit.id)[0].price == Decimal("90.00")


def test_add_service_persists_catalogue_currency(
    client, db_session, cardio_auth_headers, patient_visit,
):
    _, visit = patient_visit
    service = _make_service(db_session, price=Decimal("12.34"))
    service.currency = "USD"
    db_session.commit()

    response = _add(client, cardio_auth_headers, visit.id, service.id)
    assert response.status_code == 200, response.text
    line, = _service_rows(db_session, visit.id)
    assert (line.price, line.currency) == (Decimal("12.34"), "USD")

    other_currency = _make_service(db_session, price=Decimal("1.00"))
    denied = _add(client, cardio_auth_headers, visit.id, other_currency.id)
    assert denied.status_code == 409, denied.text
    assert len(_service_rows(db_session, visit.id)) == 1


def test_missing_catalogue_price_cannot_create_free_service(
    client, db_session, cardio_auth_headers, patient_visit,
):
    _, visit = patient_visit
    service = _make_service(db_session, price=Decimal("12.34"))
    service.price = None
    db_session.commit()

    response = _add(client, cardio_auth_headers, visit.id, service.id)
    assert response.status_code == 409, response.text
    assert _service_rows(db_session, visit.id) == []


def test_schedule_rejects_unflagged_price_override_without_side_effects(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls,
):
    patient, _ = patient_visit
    service = _make_service(db_session, price=Decimal("100.00"))
    response = _schedule(client, cardio_auth_headers, db_session, patient, service, custom_price="0.00")
    assert response.status_code == 400, response.text
    assert _pending_visits(db_session, patient_id=patient.id) == []
    assert invitation_calls == []


def test_schedule_persists_one_catalogue_currency(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls,
):
    patient, _ = patient_visit
    service = _make_service(db_session, price=Decimal("12.34"))
    service.currency = "USD"
    db_session.commit()
    response = _schedule(client, cardio_auth_headers, db_session, patient, service)
    assert response.status_code == 200, response.text
    data = response.json()
    line, = _service_rows(db_session, data["visit_id"])
    assert (line.price, line.currency, data["confirmation"]["currency"]) == (Decimal("12.34"), "USD", "USD")

    other_currency = _make_service(db_session, price=Decimal("10.00"))
    denied = _schedule(
        client, cardio_auth_headers, db_session, patient, service,
        visit_time="13:00",
        services=[
            {"service_id": service.id, "quantity": 1},
            {"service_id": other_currency.id, "quantity": 1},
        ],
    )
    assert denied.status_code == 409, denied.text
    assert len(_pending_visits(db_session, patient_id=patient.id)) == 1
    assert len(invitation_calls) == 1


@pytest.mark.parametrize("route", ["schedule", "add"])
def test_retry_of_existing_request_survives_later_deactivation(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls, route
):
    patient, visit = patient_visit
    service = _make_service(db_session, price=Decimal("123.45"))
    schedule_headers = keyed_schedule_headers(cardio_auth_headers)
    if route == "schedule":
        first = _schedule(client, schedule_headers, db_session, patient, service, custom_price="123.45")
    else:
        first = _add(client, cardio_auth_headers, visit.id, service.id, custom_price="123.45")
    assert first.status_code == 200, first.text
    service.active = False
    db_session.commit()

    if route == "schedule":
        replay = _schedule(client, schedule_headers, db_session, patient, service, custom_price="123.45")
        assert replay.status_code == 200, replay.text
        assert replay.json()["visit_id"] == first.json()["visit_id"]
        assert len(invitation_calls) == 1
    else:
        replay = _add(client, cardio_auth_headers, visit.id, service.id, custom_price="123.45")
        assert replay.status_code == 200, replay.text
        assert replay.json()["visit_service"]["id"] == first.json()["visit_service"]["id"]
        assert len(_service_rows(db_session, visit.id)) == 1
    assert replay.json()["idempotent_replay"] is True


@pytest.mark.parametrize("catalog_price", ["0.00", "123.45", "9999999999.99"])
@pytest.mark.parametrize("explicit", [False, True])
def test_catalog_price_remains_exact_for_both_entrypoints(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls, catalog_price, explicit
):
    patient, visit = patient_visit
    service = _make_service(db_session, price=Decimal(catalog_price))
    custom_price = catalog_price if explicit else None
    scheduled = _schedule(client, cardio_auth_headers, db_session, patient, service, custom_price=custom_price)
    assert scheduled.status_code == 200, scheduled.text
    scheduled_rows = _service_rows(db_session, scheduled.json()["visit_id"])
    assert len(scheduled_rows) == 1
    assert scheduled_rows[0].price == Decimal(catalog_price)
    assert len(invitation_calls) == 1

    added = _add(client, cardio_auth_headers, visit.id, service.id, custom_price=custom_price)
    assert added.status_code == 200, added.text
    rows = _service_rows(db_session, visit.id)
    assert len(rows) == 1
    assert rows[0].price == Decimal(catalog_price)


@pytest.mark.parametrize("invalid_price", ["-0.01", "0.001", "10000000000.00", "NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("route", ["schedule", "add"])
def test_invalid_custom_amount_never_persists_or_notifies(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls, route, invalid_price
):
    patient, visit = patient_visit
    service = _make_service(db_session, price=Decimal("123.45"))
    if route == "schedule":
        response = _schedule(client, cardio_auth_headers, db_session, patient, service, custom_price=invalid_price)
    else:
        response = _add(client, cardio_auth_headers, visit.id, service.id, custom_price=invalid_price)
    assert response.status_code == 422, response.text
    assert _pending_visits(db_session, patient_id=patient.id) == []
    assert _service_rows(db_session, visit.id) == []
    assert invitation_calls == []


@pytest.mark.parametrize("route", ["schedule", "add"])
def test_high_precision_string_is_not_rounded_to_catalog_price(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls, route
):
    patient, visit = patient_visit
    service = _make_service(db_session, price=Decimal("123.45"))
    high_precision = "123.450000000000000000000001"
    if route == "schedule":
        response = _schedule(client, cardio_auth_headers, db_session, patient, service, custom_price=high_precision)
    else:
        response = _add(client, cardio_auth_headers, visit.id, service.id, custom_price=high_precision)
    assert response.status_code == 422, response.text
    assert _pending_visits(db_session, patient_id=patient.id) == []
    assert _service_rows(db_session, visit.id) == []
    assert invitation_calls == []


def test_catalog_equal_json_number_is_accepted_without_rounding(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls
):
    patient, _ = patient_visit
    service = _make_service(db_session, price=Decimal("123.45"))
    response = _schedule(client, cardio_auth_headers, db_session, patient, service, custom_price=123.45)
    assert response.status_code == 200, response.text
    rows = _service_rows(db_session, response.json()["visit_id"])
    assert len(rows) == 1 and rows[0].price == Decimal("123.45")
    assert len(invitation_calls) == 1


@pytest.mark.parametrize(
    "raw_value,expected",
    [
        ("123.450000000000000001", 422),
        ("1e-1000", 422),
        ("NaN", 422),
        ("Infinity", 422),
        ("-Infinity", 422),
        ("123.45", 200),
        ('"123.45"', 200),
        ('123.45,"custom_price":0.001', 422),
        ('0.001,"custom_price":123.45', 200),
    ],
)
def test_raw_json_price_preserves_precision_and_duplicate_key_semantics(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls, raw_value, expected
):
    patient, _ = patient_visit
    service = _make_service(db_session, price=Decimal("123.45"))
    payload = _schedule_payload(
        patient, service, visit_date=_clinic_today(db_session) + timedelta(days=1), services=[]
    )
    body = json.dumps(payload).replace(
        '"services": []',
        f'"services": [{{"service_id": {service.id}, "quantity": 1, "custom_price": {raw_value}}}]',
    )
    response = client.post(
        "/api/v1/doctor/visits/schedule-next",
        content=body,
        headers={**cardio_auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == expected, response.text
    pending = _pending_visits(db_session, patient_id=patient.id)
    if expected == 200:
        assert len(pending) == 1
        assert _service_rows(db_session, pending[0].id)[0].price == Decimal("123.45")
        assert len(invitation_calls) == 1
    else:
        assert pending == []
        assert invitation_calls == []


def test_malformed_json_has_no_side_effects(client, db_session, cardio_auth_headers, patient_visit, invitation_calls):
    patient, _ = patient_visit
    response = client.post(
        "/api/v1/doctor/visits/schedule-next",
        content='{"services": [}',
        headers={**cardio_auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code in (400, 422), response.text
    assert _pending_visits(db_session, patient_id=patient.id) == []
    assert invitation_calls == []


@pytest.mark.parametrize("route", ["schedule", "add"])
@pytest.mark.parametrize("price,quantity", [("1.00", 2147483648), ("9999999999.99", 2)])
def test_quantity_or_extended_price_overflow_is_rejected_without_side_effects(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls, route, price, quantity
):
    patient, visit = patient_visit
    service = _make_service(db_session, price=Decimal(price))
    if route == "schedule":
        response = _schedule(client, cardio_auth_headers, db_session, patient, service, quantity=quantity)
    else:
        response = _add(client, cardio_auth_headers, visit.id, service.id, quantity=quantity)
    assert response.status_code == 422, response.text
    assert _pending_visits(db_session, patient_id=patient.id) == []
    assert _service_rows(db_session, visit.id) == []
    assert invitation_calls == []


def test_sum_of_multiple_scheduled_lines_must_fit_invoice_numeric(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls
):
    patient, _ = patient_visit
    first = _make_service(db_session, price=Decimal("5000000000.00"))
    second = _make_service(db_session, price=Decimal("5000000000.00"))
    response = _schedule(client, cardio_auth_headers, db_session, patient, first, services=[
        {"service_id": first.id, "quantity": 1}, {"service_id": second.id, "quantity": 1}
    ])
    assert response.status_code == 422, response.text
    assert _pending_visits(db_session, patient_id=patient.id) == []
    assert invitation_calls == []


def test_adding_line_cannot_overflow_existing_visit_total(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls
):
    _, visit = patient_visit
    first = _make_service(db_session, price=Decimal("6000000000.00"))
    second = _make_service(db_session, price=Decimal("5000000000.00"))
    db_session.add(VisitService(visit_id=visit.id, service_id=first.id, name=first.name,
                                qty=1, price=first.price, currency="UZS"))
    db_session.commit()
    old_ids = {row.id for row in _service_rows(db_session, visit.id)}
    response = _add(client, cardio_auth_headers, visit.id, second.id)
    assert response.status_code == 422, response.text
    assert {row.id for row in _service_rows(db_session, visit.id)} == old_ids
    assert invitation_calls == []


def test_aggregate_at_numeric_limit_is_accepted_exactly(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls
):
    patient, _ = patient_visit
    first = _make_service(db_session, price=Decimal("5000000000.00"))
    second = _make_service(db_session, price=Decimal("4999999999.99"))
    response = _schedule(client, cardio_auth_headers, db_session, patient, first, services=[
        {"service_id": first.id, "quantity": 1}, {"service_id": second.id, "quantity": 1}
    ])
    assert response.status_code == 200, response.text
    rows = _service_rows(db_session, response.json()["visit_id"])
    assert sum((row.price * row.qty for row in rows), Decimal("0")) == Decimal("9999999999.99")
    assert len(invitation_calls) == 1


@pytest.mark.parametrize("route", ["schedule", "add"])
def test_catalog_change_makes_implicit_price_retry_ambiguous(
    client, db_session, cardio_auth_headers, patient_visit, invitation_calls, route
):
    patient, visit = patient_visit
    service = _make_service(db_session, price=Decimal("100000000.00"))
    if route == "schedule":
        first = _schedule(client, cardio_auth_headers, db_session, patient, service)
    else:
        first = _add(client, cardio_auth_headers, visit.id, service.id)
    assert first.status_code == 200, first.text

    service.price = Decimal("100000000.01")
    db_session.commit()
    if route == "schedule":
        second = _schedule(client, cardio_auth_headers, db_session, patient, service)
        assert len(invitation_calls) == 1
        assert len(_pending_visits(db_session, patient_id=patient.id)) == 1
    else:
        second = _add(client, cardio_auth_headers, visit.id, service.id)
        assert len(_service_rows(db_session, visit.id)) == 1
    assert second.status_code == 409, second.text


def test_retry_price_matching_distinguishes_one_cent_at_large_values():
    from app.api.v1.endpoints.doctor_integration._visits import (
        _schedule_next_service_lines_match,
    )

    stored = [VisitService(service_id=123, qty=1, price=Decimal("100000000.00"))]
    assert _schedule_next_service_lines_match(stored, [(123, 1, Decimal("100000000.00"))])
    assert not _schedule_next_service_lines_match(stored, [(123, 1, Decimal("100000000.01"))])
