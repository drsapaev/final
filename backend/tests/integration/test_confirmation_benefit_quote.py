"""The public review shows the same exact aggregate as payment."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.discount_benefits import Benefit, BenefitType, PatientBenefit
from app.models.encounter import Encounter
from app.models.encounter_benefit_ledger import (
    EncounterBenefitAllocation,
    EncounterBenefitApplication,
    EncounterBenefitVisitSnapshot,
)
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService


def _discounted_review(db):
    actor = User(username="synthetic-review-admin", hashed_password="!", role="Admin", is_active=True)
    patient = Patient(first_name="SYNTHETIC", last_name="REVIEW")
    service = Service(code="SYNTHETIC-REVIEW", name="SYNTHETIC", price=Decimal("0.07"), active=True)
    benefit = Benefit(name="SYNTHETIC", benefit_type=BenefitType.EMPLOYEE, discount_percentage=50, is_active=True)
    db.add_all([actor, patient, service, benefit])
    db.flush()
    assignment = PatientBenefit(patient_id=patient.id, benefit_id=benefit.id, is_active=True, verified=True)
    encounter = Encounter(patient_id=patient.id, provenance="new")
    db.add_all([assignment, encounter])
    db.flush()
    visit = Visit(patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2099, 1, 1),
                  status="pending_confirmation", confirmation_channel="pwa",
                  confirmation_token="SYNTHETIC-review-benefit-token",
                  confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1), confirmation_context_epoch=1)
    sibling = Visit(patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2099, 1, 1),
                    confirmation_context_epoch=1)
    db.add_all([visit, sibling])
    db.flush()
    line = VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC", qty=3,
                        price=Decimal("0.07"), currency="UZS")
    db.add(line)
    db.flush()
    application = EncounterBenefitApplication(
        encounter_id=encounter.id, patient_id=patient.id, patient_id_snapshot=patient.id,
        patient_benefit_id=assignment.id, patient_benefit_id_snapshot=assignment.id,
        benefit_id=benefit.id, benefit_id_snapshot=benefit.id,
        approved_by_user_id=actor.id, approved_by_user_id_snapshot=actor.id,
        approved_by_role_snapshot="Admin", period_timezone="Asia/Tashkent", period_month=date(2099, 1, 1),
        period_year=2099, encounter_generation=encounter.generation, percentage=Decimal("50"),
        monthly_used_before=Decimal("0"), yearly_used_before=Decimal("0"), gross_total=Decimal("0.21"),
        benefit_total=Decimal("0.10"), net_total=Decimal("0.11"),
    )
    db.add(application)
    db.flush()
    for item in (visit, sibling):
        db.add(EncounterBenefitVisitSnapshot(application_id=application.id, visit_id=item.id,
            encounter_id=encounter.id, patient_id=patient.id, visit_id_snapshot=item.id, visit_context_epoch=1))
    db.add(EncounterBenefitAllocation(application_id=application.id, visit_id=visit.id, visit_id_snapshot=visit.id,
        visit_service_id=line.id, visit_service_id_snapshot=line.id, service_id_snapshot=service.id, visit_context_epoch=1,
        quantity=3, unit_price=Decimal("0.07"), gross_amount=Decimal("0.21"), benefit_amount=Decimal("0.10"),
        net_amount=Decimal("0.11")))
    db.commit()
    return visit.id, line.id


def test_http_review_shows_exact_net_and_refuses_stale_evidence(client, db_session):
    visit_id, line_id = _discounted_review(db_session)
    token = "SYNTHETIC-review-benefit-token"
    response = client.post("/api/v1/visits/info", json={"token": token})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["visit_id"] == visit_id
    assert body["total_amount"] == 0.11
    assert body["services"][0]["quantity"] == 3
    assert body["services"][0]["price"] == 0.07
    assert body["services"][0]["total"] == 0.11
    line = db_session.get(VisitService, line_id)
    line.price = Decimal("0.08")
    db_session.commit()
    stale = client.post("/api/v1/visits/info", json={"token": token})
    assert stale.status_code == 409


@pytest.mark.parametrize("price,status,total", [
    (None, 409, None),
    (Decimal("0.00"), 200, 0.0),
    (Decimal("0.07"), 200, 0.21),
])
def test_http_review_distinguishes_missing_zero_and_regular_prices(client, db_session, test_visit, price, status, total):
    db_session.add(VisitService(visit_id=test_visit.id, service_id=1, name="SYNTHETIC", qty=3,
                                price=price, currency="UZS"))
    db_session.commit()
    response = client.post("/api/v1/visits/info", json={"token": test_visit.confirmation_token})
    assert response.status_code == status
    if total is not None:
        assert response.json()["total_amount"] == total


@pytest.mark.parametrize("currency", [None, "USD", "UZS"])
def test_http_review_preserves_verified_currency(client, db_session, test_visit, currency):
    db_session.add(VisitService(visit_id=test_visit.id, service_id=1, name="SYNTHETIC", qty=1,
                                price=Decimal("1.00"), currency=currency))
    db_session.commit()
    response = client.post("/api/v1/visits/info", json={"token": test_visit.confirmation_token})
    assert response.status_code == 200, response.text
    assert response.json()["currency"] == currency


def test_http_review_refuses_mixed_currencies(client, db_session, test_visit):
    for currency in ("UZS", "USD"):
        db_session.add(VisitService(visit_id=test_visit.id, service_id=1, name="SYNTHETIC", qty=1,
                                    price=Decimal("1.00"), currency=currency))
    db_session.commit()
    response = client.post("/api/v1/visits/info", json={"token": test_visit.confirmation_token})
    assert response.status_code == 409


@pytest.mark.parametrize("currency,expected", [(None, 409), ("USD", 200)])
def test_confirmation_requires_verified_currency(client, db_session, test_visit, test_daily_queue, currency, expected):
    test_visit.confirmation_channel = "pwa"
    db_session.add(VisitService(visit_id=test_visit.id, service_id=1, name="SYNTHETIC", qty=1,
                                price=Decimal("1.00"), currency=currency))
    db_session.commit()
    token = test_visit.confirmation_token
    response = client.post("/api/v1/patient/visits/confirm", json={"token": token})
    assert response.status_code == expected, response.text
    db_session.expire_all()
    visit = db_session.get(Visit, test_visit.id)
    if currency is None:
        assert visit.status == "pending_confirmation"
        assert visit.confirmation_token == token
    else:
        assert visit.status in {"confirmed", "open"}


def test_telegram_confirmation_requires_verified_currency(db_session, test_visit, test_daily_queue, monkeypatch):
    from app.services.visit_confirmation_service import VisitConfirmationDomainError
    from tests.integration.test_visit_confirmation_api import (
        _link_patient_chat,
        _trusted_confirm,
    )

    monkeypatch.setattr("app.tasks.worker._appointment_start_utc", lambda visit: datetime.now(UTC) + timedelta(days=1))
    test_visit.confirmation_channel = "telegram"
    db_session.add(VisitService(visit_id=test_visit.id, service_id=1, name="SYNTHETIC", qty=1,
                                price=Decimal("1.00"), currency=None))
    db_session.flush()
    db_session.refresh(test_visit)
    test_visit.confirmation_token = "SYNTHETIC-telegram-currency-token"
    _link_patient_chat(db_session, test_visit)
    token = test_visit.confirmation_token
    with pytest.raises(VisitConfirmationDomainError) as error:
        _trusted_confirm(db_session, token)
    assert error.value.status_code == 409
    db_session.expire_all()
    visit = db_session.get(Visit, test_visit.id)
    assert visit.status == "pending_confirmation"
    assert visit.confirmation_token == token
