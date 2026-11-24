"""Synthetic registrar repeat evidence and trusted pricing checks."""
from datetime import date, timedelta
from decimal import ROUND_UP, Decimal, Inexact, Rounded, localcontext

import pytest

from app.crud.clinic import clinic_today
from app.models.payment_invoice import PaymentInvoice
from app.models.visit import VisitService
from tests.integration.test_docsched_repeat_policy import _prior, _setting
from tests.integration.test_docsched_schedule_next_integrity import _make_service
from tests.integration.test_registrar_cart_encounter_grouping import (
    _counts,
    _headers,
    _service,
    _visit,
)

pytestmark = pytest.mark.integration


def test_repeat_quote_rounding_does_not_depend_on_caller_decimal_context():
    from app.api.v1.endpoints.registrar_wizard._helpers import _apply_service_discount

    with localcontext() as context:
        context.prec = 1
        context.rounding = ROUND_UP
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        price = _apply_service_discount(Decimal("0.05"), "repeat", {"repeat_visit_discount": 10}, True)
        assert price == Decimal("0.04")
        assert context.prec == 1 and context.rounding == ROUND_UP


def _repeat_payload(patient_id, doctor_id, service_id, target):
    visit = _visit(service_id, target)
    visit["doctor_id"] = doctor_id
    return {"patient_id": patient_id, "discount_mode": "repeat", "payment_method": "cash", "visits": [visit]}


def test_cart_repeat_uses_completed_same_doctor_and_persists_currency(
    client, db_session, admin_user, test_patient, test_doctor
):
    today = clinic_today(db_session)
    service = _make_service(db_session, price=Decimal("123.45"), is_consultation=True)
    _setting(db_session, "repeat_visit_days", 21)
    _setting(db_session, "repeat_visit_discount", 20)
    _prior(db_session, test_patient, test_doctor, service, today - timedelta(days=2))
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json=_repeat_payload(test_patient.id, test_doctor.id, service.id, today + timedelta(days=2)))
    assert response.status_code == 200, response.text
    db_session.expire_all()
    line = db_session.query(VisitService).filter_by(visit_id=response.json()["visit_ids"][0]).one()
    invoice = db_session.get(PaymentInvoice, response.json()["invoice_id"])
    assert line.price == invoice.total_amount == Decimal("98.76")
    assert line.currency == invoice.currency == service.currency


@pytest.mark.parametrize("case", ["incomplete", "outside_target", "wrong_doctor", "no_doctor"])
def test_cart_rejects_repeat_without_qualifying_evidence(
    client, db_session, admin_user, test_patient, test_doctor, case
):
    today = clinic_today(db_session)
    service = _make_service(db_session, is_consultation=True)
    _setting(db_session, "repeat_visit_days", 21)
    prior = _prior(db_session, test_patient, test_doctor, service, today - timedelta(days=2),
                   status="in_progress" if case == "incomplete" else "completed")
    if case == "wrong_doctor":
        prior.repeat_proof_doctor_user_id = test_doctor.user_id + 9999
        db_session.commit()
    before = _counts(db_session, test_patient.id)
    target = today + timedelta(days=21) if case == "outside_target" else today + timedelta(days=2)
    doctor_id = None if case == "no_doctor" else test_doctor.id
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json=_repeat_payload(test_patient.id, doctor_id, service.id, target))
    assert response.status_code in {400, 409, 422}, response.text
    db_session.expire_all()
    assert _counts(db_session, test_patient.id) == before


def test_cart_rejects_mixed_catalog_currencies_without_writes(client, db_session, admin_user, test_patient):
    first, second = _service(db_session), _service(db_session)
    first.currency, second.currency = "UZS", "USD"
    db_session.commit()
    day = clinic_today(db_session) + timedelta(days=3)
    visit = _visit(first.id, day)
    visit["services"].append({"service_id": second.id, "quantity": 1})
    before = _counts(db_session, test_patient.id)
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json={"patient_id": test_patient.id, "visits": [visit], "discount_mode": "none"})
    assert response.status_code == 409, response.text
    db_session.expire_all()
    assert _counts(db_session, test_patient.id) == before


def test_unreviewed_custom_price_cannot_create_confirmed_zero_visit(client, db_session, admin_user, test_patient):
    service = _service(db_session)
    visit = _visit(service.id, clinic_today(db_session) + timedelta(days=3))
    visit["services"][0]["custom_price"] = "0.00"
    before = _counts(db_session, test_patient.id)
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json={"patient_id": test_patient.id, "visits": [visit], "discount_mode": "none"})
    assert response.status_code == 409, response.text
    db_session.expire_all()
    assert _counts(db_session, test_patient.id) == before


@pytest.mark.parametrize("price,quantity", [("6000000000.00", 2), ("1.00", 2147483648)])
def test_cart_rejects_unrepresentable_amount_or_quantity_atomically(
    client, db_session, admin_user, test_patient, price, quantity
):
    service = _service(db_session)
    service.price = Decimal(price)
    db_session.commit()
    visit = _visit(service.id, clinic_today(db_session) + timedelta(days=3))
    visit["services"][0]["quantity"] = quantity
    before = _counts(db_session, test_patient.id)
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json={"patient_id": test_patient.id, "visits": [visit], "discount_mode": "none"})
    assert response.status_code == 422, response.text
    db_session.expire_all()
    assert _counts(db_session, test_patient.id) == before


def test_cart_quote_currency_change_invalidates_confirmation(client, db_session, admin_user, test_patient):
    service = _service(db_session)
    service.currency = "USD"
    db_session.commit()
    item = {"service_id": service.id, "quantity": 1}
    quote = client.post("/api/v1/registrar/cart/quote", headers=_headers(admin_user),
                        json={"items": [item], "discount_mode": "none", "pricing_mode": "cart"})
    assert quote.status_code == 200, quote.text
    assert quote.json()["currency"] == "USD"
    service.currency = "UZS"
    db_session.commit()
    before = _counts(db_session, test_patient.id)
    visit = _visit(service.id, clinic_today(db_session) + timedelta(days=3))
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json={"patient_id": test_patient.id, "visits": [visit], "discount_mode": "none",
                                 "quote_token": quote.json()["quote_token"]})
    assert response.status_code == 409, response.text
    db_session.expire_all()
    assert _counts(db_session, test_patient.id) == before


def test_mixed_currency_quote_is_not_presented_as_one_total(client, db_session, admin_user):
    first, second = _service(db_session), _service(db_session)
    first.currency, second.currency = "UZS", "USD"
    db_session.commit()
    response = client.post("/api/v1/registrar/cart/quote", headers=_headers(admin_user),
                           json={"items": [{"service_id": first.id}, {"service_id": second.id}],
                                 "discount_mode": "none", "pricing_mode": "cart"})
    assert response.status_code == 409, response.text


def test_sqlite_normal_cart_reserves_writer_before_reading_catalog(tmp_path, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace

    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import DBAPIError
    from sqlalchemy.orm import Session

    import app.db.base  # noqa: F401 — register full metadata
    from app.api.v1.endpoints.registrar_wizard import _cart
    from app.api.v1.endpoints.registrar_wizard._helpers import CartRequest
    from app.db.base_class import Base
    from app.models.service import Service
    from app.models.visit import Visit
    from tests.integration.test_repeat_completion_catalog_race_pg import _case

    engine = create_engine(f"sqlite:///{tmp_path / 'cart.sqlite'}", connect_args={"timeout": 0.1})
    try:
        Base.metadata.create_all(engine)
        prior_id, service_id = _case(engine)
        with Session(engine) as db:
            prior = db.get(Visit, prior_id)
            patient_id = prior.patient_id
            service = db.get(Service, service_id)
            service.is_consultation = False
            service.requires_doctor = False
            db.commit()
        entered, release = threading.Event(), threading.Event()
        original = _cart._assert_cart_doctor_eligibility

        def pause_after_reservation(db, visits, **kwargs):
            if not entered.is_set():
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("synthetic test barrier timed out")
            return original(db, visits, **kwargs)

        monkeypatch.setattr(_cart, "_assert_cart_doctor_eligibility", pause_after_reservation)
        payload = CartRequest.model_validate(_repeat_payload(patient_id, None, service_id, date.today() + timedelta(days=3)))
        payload.discount_mode = "none"

        def create_cart():
            with Session(engine) as db:
                return _cart.create_cart_appointments(payload, db=db, current_user=SimpleNamespace(id=1, role="Admin"))

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(create_cart)
            try:
                assert entered.wait(10)
                with Session(engine) as writer:
                    with pytest.raises(DBAPIError) as error:
                        writer.execute(text("UPDATE services SET price=200 WHERE id=:id"), {"id": service_id})
                    assert error.value.orig.sqlite_errorcode & 0xff in {5, 6}
                    writer.rollback()
            finally:
                release.set()
            result = future.result(timeout=10)
            assert result.total_amount == Decimal("100.00")
    finally:
        engine.dispose()


def test_unapproved_benefit_quote_does_not_advertise_free_service(client, db_session, admin_user):
    service = _service(db_session)
    response = client.post("/api/v1/registrar/cart/quote", headers=_headers(admin_user),
                           json={"items": [{"service_id": service.id}], "discount_mode": "benefit", "pricing_mode": "cart"})
    assert response.status_code == 409, response.text
