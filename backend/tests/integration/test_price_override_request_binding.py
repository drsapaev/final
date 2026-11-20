"""Issuer binding checks, with only synthetic users and mocked delivery."""
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.models.doctor_price_override import DoctorPriceOverride
from app.models.visit import VisitService
from app.services.dental_api_service import DentalApiService
from tests.conftest import mint_access_token
from tests.integration.test_derma_price_override_integrity import (
    _create_doctor,
    _create_patient,
    _create_service,
    _create_user,
    _create_visit_with_service,
    _suffix,
)


@pytest.fixture
def issuer(client, db_session, monkeypatch, request):
    dental = request.param == "dental"
    user = _create_user(db_session, role="dentist" if dental else "derma", label="bound")
    doctor = _create_doctor(db_session, user, specialty="dental" if dental else "dermatology")
    doctor.repeat_owner_generation = 42
    patient = _create_patient(db_session)
    service = _create_service(db_session, label=_suffix(), price=Decimal("200.00"))
    visit, line = _create_visit_with_service(db_session, patient=patient, doctor=doctor, service=service, price=Decimal("123.45"))
    visit.confirmation_context_epoch = 43
    db_session.commit()
    monkeypatch.setattr(DentalApiService, "send_price_override_notification", AsyncMock())
    return {"client": client, "db": db_session, "user": user, "doctor": doctor,
            "visit": visit, "service": service, "line": line,
            "path": f"/api/v1/{request.param}/price-override",
            "headers": {"Authorization": f"Bearer {mint_access_token(user)}", "Content-Type": "application/json"}}


def _post(f, raw_price, *, extras=""):
    payload = (
        f'{{"visit_id":{f["visit"].id},"service_id":{f["service"].id},'
        f'"new_price":{raw_price},"reason":"synthetic"{extras}}}'
    )
    return f["client"].post(f["path"], headers=f["headers"], content=payload)


@pytest.mark.parametrize("issuer", ["derma", "dental"], indirect=True)
@pytest.mark.parametrize("price", ["0", "123.45", '"123.45"'])
def test_exact_price_is_bound_and_zero_accepted(issuer, price):
    response = _post(issuer, price)
    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["new_price"])) == Decimal(price.strip('"'))
    row = issuer["db"].query(DoctorPriceOverride).one()
    assert row.status == "pending"
    assert row.target_scope == "visit_service"
    assert row.target_visit_service_id == issuer["line"].id
    assert row.visit_context_epoch == 43
    assert row.doctor_owner_user_id == issuer["user"].id
    assert row.doctor_owner_generation == 42
    assert row.price_context_generation == issuer["visit"].price_context_generation
    assert row.price_line_generation == issuer["line"].price_line_generation
    assert row.price_owner_generation == issuer["doctor"].price_owner_generation
    assert row.requester_type == "doctor"
    assert row.requester_user_id == row.requester_user_id_snapshot == issuer["user"].id
    assert row.requester_auth_epoch == row.doctor_user_auth_epoch == issuer["user"].auth_epoch
    assert row.visit_price_before == Decimal("123.45")
    assert issuer["line"].price == Decimal("123.45")


@pytest.mark.parametrize("issuer", ["derma", "dental"], indirect=True)
def test_unbound_legacy_pending_blocks_new_request_until_reviewed(issuer):
    db = issuer["db"]
    db.add(DoctorPriceOverride(
        visit_id=issuer["visit"].id, doctor_id=issuer["doctor"].id,
        service_id=issuer["service"].id, original_price=Decimal("123.45"),
        new_price=Decimal("1.00"), reason="legacy synthetic", status="pending",
    ))
    db.commit()
    assert _post(issuer, "0").status_code == 409
    assert db.query(DoctorPriceOverride).count() == 1


@pytest.mark.parametrize("issuer", ["derma", "dental"], indirect=True)
@pytest.mark.parametrize("price", ["123.450000000000000001", "1e-1000", "NaN", "Infinity", "-0.01", "10000000000", "true"])
def test_unrepresentable_json_money_has_no_side_effect(issuer, price):
    response = _post(issuer, price)
    # Global validation handler returns 400 for non-JSON NaN/Infinity when
    # serializing the initial FastAPI validation error.
    assert response.status_code in (400, 422), response.text
    assert issuer["db"].query(DoctorPriceOverride).count() == 0


@pytest.mark.parametrize("issuer", ["derma", "dental"], indirect=True)
def test_duplicate_lines_require_explicit_target_and_duplicate_pending_conflicts(issuer):
    db, line = issuer["db"], issuer["line"]
    second = VisitService(visit_id=line.visit_id, service_id=line.service_id,
                          code=line.code, name=line.name, qty=1, price=Decimal("100.00"))
    db.add(second)
    db.commit()
    assert _post(issuer, "0").status_code == 409
    result = _post(issuer, "0", extras=f',"target_visit_service_id":{second.id}')
    assert result.status_code == 200, result.text
    assert db.query(DoctorPriceOverride).one().target_visit_service_id == second.id
    assert _post(issuer, "0", extras=f',"target_visit_service_id":{line.id}').status_code == 200
    assert {row.target_visit_service_id for row in db.query(DoctorPriceOverride).all()} == {line.id, second.id}
    assert _post(issuer, "0", extras=f',"target_visit_service_id":{line.id}').status_code == 409


@pytest.mark.parametrize("issuer", ["derma", "dental"], indirect=True)
def test_inactive_service_and_doctor_are_refused(issuer):
    issuer["service"].active = False
    issuer["db"].commit()
    assert _post(issuer, "10").status_code == 400
    issuer["service"].active = True
    issuer["doctor"].active = False
    issuer["db"].commit()
    assert _post(issuer, "10").status_code == 403
    assert issuer["db"].query(DoctorPriceOverride).count() == 0


@pytest.mark.parametrize("issuer", ["derma", "dental"], indirect=True)
def test_duplicate_json_key_uses_last_value(issuer):
    assert _post(issuer, "1e-1000", extras=',"new_price":1.00').status_code == 200


@pytest.mark.parametrize("issuer", ["derma", "dental"], indirect=True)
def test_duplicate_json_key_rejects_invalid_last_value(issuer):
    assert _post(issuer, "1.00", extras=',"new_price":1e-1000').status_code == 422
    assert issuer["db"].query(DoctorPriceOverride).count() == 0


@pytest.mark.parametrize("issuer", ["derma", "dental"], indirect=True)
def test_malformed_json_and_wrong_target_have_no_effect(issuer):
    bad_json = issuer["client"].post(issuer["path"], headers=issuer["headers"], content="{")
    assert bad_json.status_code in (400, 422)
    assert _post(issuer, "1.00", extras=',"target_visit_service_id":999999').status_code == 409
    assert issuer["db"].query(DoctorPriceOverride).count() == 0


@pytest.mark.parametrize("issuer", ["derma", "dental"], indirect=True)
def test_missing_visit_price_and_generation_fail_closed(issuer):
    issuer["line"].price = None
    issuer["db"].commit()
    assert _post(issuer, "1.00").status_code == 409
    issuer["line"].price = Decimal("123.45")
    issuer["visit"].confirmation_context_epoch = 0
    issuer["db"].commit()
    assert _post(issuer, "1.00").status_code == 409
    assert issuer["db"].query(DoctorPriceOverride).count() == 0


@pytest.mark.parametrize("route", ["derma", "dental"])
def test_sqlite_concurrent_issuers_serialize(tmp_path, monkeypatch, route):
    import asyncio
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from datetime import date
    from types import SimpleNamespace

    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import Session

    from app.db.base_class import Base
    from app.models.clinic import Doctor
    from app.models.patient import Patient
    from app.models.service import Service
    from app.models.user import User
    from app.models.visit import Visit
    from app.services.dental_api_service import DentalApiDomainError
    from app.services.derma_api_service import DermaApiDomainError, DermaApiService
    from app.services.profile_contact_security import ProfileBearerContext

    engine = create_engine(f"sqlite:///{tmp_path / 'race.sqlite'}", connect_args={"timeout": 10})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(DentalApiService, "send_price_override_notification", AsyncMock())
    with Session(engine, expire_on_commit=False) as db:
        user = User(username="synthetic_race", hashed_password="!", role="derma" if route == "derma" else "dentist", is_active=True)
        patient = Patient(first_name="Synthetic", last_name="Race", birth_date=date(1990, 1, 1), phone="+998900000002")
        service = Service(code="race", name="Synthetic", price=Decimal("10.00"), active=True, allow_doctor_price_override=True, duration_minutes=10)
        db.add_all([user, patient, service])
        db.flush()
        doctor = Doctor(user_id=user.id, specialty="dermatology" if route == "derma" else "dental", active=True, repeat_owner_generation=11)
        db.add(doctor)
        db.flush()
        visit = Visit(patient_id=patient.id, doctor_id=doctor.id, visit_date=date(2099, 1, 1), status="open", source="desk", confirmation_context_epoch=12)
        db.add(visit)
        db.flush()
        line = VisitService(visit_id=visit.id, service_id=service.id, code=service.code, name=service.name, qty=1, price=Decimal("10.00"))
        db.add(line)
        db.flush()
        ids = user.id, visit.id, service.id
        db.commit()

    holding, release, second_at_reservation = threading.Event(), threading.Event(), threading.Event()
    first_id, second_id = [], []

    def on_query(_conn, _cursor, statement, _parameters, _context, _many):
        thread = threading.get_ident()
        if thread in first_id and "from services" in statement.lower() and not holding.is_set():
            holding.set()
            if not release.wait(10):
                raise AssertionError("release timed out")
        if thread in second_id and "update users set id=id where 0" in statement.lower():
            second_at_reservation.set()

    def issue(marker):
        marker.append(threading.get_ident())
        with Session(engine, expire_on_commit=False) as db:
            bearer = ProfileBearerContext(ids[0], 0, None, int(time.time()) + 60, None)
            data = SimpleNamespace(visit_id=ids[1], service_id=ids[2], new_price=Decimal("5.00"), reason="synthetic", details=None, target_visit_service_id=None)
            try:
                if route == "derma":
                    DermaApiService(db).create_price_override(override_data=data, user_id=ids[0], bearer=bearer)
                else:
                    asyncio.run(DentalApiService(db).create_dental_price_override(override_data=data, user=SimpleNamespace(id=ids[0]), bearer=bearer))
                return 200
            except (DermaApiDomainError, DentalApiDomainError) as exc:
                return exc.status_code

    event.listen(engine, "before_cursor_execute", on_query)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(issue, first_id)
            assert holding.wait(5)
            second = pool.submit(issue, second_id)
            try:
                assert second_at_reservation.wait(5)
                assert not second.done()
            finally:
                release.set()
            assert [first.result(timeout=12), second.result(timeout=12)] == [200, 409]
        with Session(engine) as db:
            assert db.query(DoctorPriceOverride).filter_by(status="pending").count() == 1
    finally:
        release.set()
        event.remove(engine, "before_cursor_execute", on_query)
        engine.dispose()
