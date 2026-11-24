"""Payment totals consume one exact, complete benefit snapshot."""
from datetime import date
from decimal import Decimal, localcontext
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base_class import Base
from app.models.discount_benefits import Benefit, BenefitType, PatientBenefit
from app.models.encounter import Encounter
from app.models.encounter_benefit_ledger import (
    EncounterBenefitAllocation,
    EncounterBenefitApplication,
    EncounterBenefitVisitSnapshot,
)
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.notifications_pkg._formatting import FormattingMixin
from app.services.payment_invariant_service import PaymentInvariantService


def test_sqlite_snapshot_refreshes_previously_loaded_line(tmp_path):
    import app.db.base  # noqa: F401

    engine = create_engine(f"sqlite:///{tmp_path / 'quote.sqlite'}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as first:
            patient = Patient(first_name="SYNTHETIC", last_name="Snapshot")
            service = Service(code="SYNTHETIC-SSOT-STALE", name="SYNTHETIC", price=Decimal("0.07"), active=True)
            first.add_all([patient, service])
            first.flush()
            visit = Visit(patient_id=patient.id, visit_date=date(2099, 1, 1), confirmation_context_epoch=1)
            first.add(visit)
            first.flush()
            line = VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC", qty=3,
                                price=Decimal("0.07"), currency="UZS")
            first.add(line)
            first.commit()
            with Session(engine) as second:
                second.get(VisitService, line.id).price = Decimal("0.09")
                second.commit()
            assert line.price == Decimal("0.07")
            assert PaymentInvariantService(first).compute_total_cost(visit) == Decimal("0.27")
            assert line.price == Decimal("0.09")
            first.commit()  # release the SQLite writer while retaining the cached Visit
            original_patient = visit.patient_id
            with Session(engine) as second:
                replacement = Patient(first_name="SYNTHETIC", last_name="Replacement")
                second.add(replacement)
                second.flush()
                changed = second.get(Visit, visit.id)
                changed.patient_id = replacement.id
                changed.confirmation_context_epoch = 2
                second.commit()
            assert visit.patient_id == original_patient
            with pytest.raises(HTTPException) as error:
                PaymentInvariantService(first).compute_visit_quote(visit)
            assert error.value.status_code == 409
            assert visit.patient_id != original_patient  # refresh did not erase the pre-refresh comparison
    finally:
        engine.dispose()


def test_unadjusted_and_zero_lines_are_exact(db_session):
    patient = Patient(first_name="SYNTHETIC", last_name="Money")
    service = Service(code="SYNTHETIC-SSOT-PLAIN", name="SYNTHETIC", price=Decimal("0.07"), active=True)
    db_session.add_all([patient, service])
    db_session.flush()
    visit = Visit(patient_id=patient.id, visit_date=date(2099, 1, 1), confirmation_context_epoch=1)
    db_session.add(visit)
    db_session.flush()
    lines = [VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC",
                          qty=3, price=Decimal("0.07"), currency="UZS"),
             VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC",
                          qty=1, price=Decimal("0.00"), currency="UZS")]
    db_session.add_all(lines)
    db_session.flush()
    quote = PaymentInvariantService(db_session).compute_visit_quote(visit)
    assert quote.total == Decimal("0.21")
    assert quote.currency == "UZS"
    assert dict(quote.line_totals) == {lines[0].id: Decimal("0.21"), lines[1].id: Decimal("0.00")}
    assert PaymentInvariantService(db_session).compute_total_cost(visit) == Decimal("0.21")
    with localcontext() as context:
        context.prec = 1
        assert PaymentInvariantService(db_session).compute_total_cost(visit) == Decimal("0.21")
    lines[1].currency = None
    db_session.flush()
    assert PaymentInvariantService(db_session).compute_visit_quote(visit).currency is None
    with pytest.raises(ValueError, match="Валюта"):
        FormattingMixin()._prepare_notification_data(db_session, visit, patient)
    lines[1].currency = "USD"
    db_session.flush()
    with pytest.raises(HTTPException) as error:
        PaymentInvariantService(db_session).compute_visit_quote(visit)
    assert error.value.status_code == 409
    lines[0].currency = "USD"
    db_session.flush()
    usd = FormattingMixin()._prepare_notification_data(db_session, visit, patient)
    assert usd["currency"] == "USD"
    assert usd["services"] == ["• SYNTHETIC × 3 - 0.21 USD", "• SYNTHETIC - 0.00 USD"]


def test_discounted_quantity_and_stale_evidence_fail_closed(db_session):
    actor = User(username="synthetic-benefit-ssot", hashed_password="!", role="Admin", is_active=True)
    patient = Patient(first_name="SYNTHETIC", last_name="Benefit")
    service = Service(code="SYNTHETIC-SSOT-BENEFIT", name="SYNTHETIC", price=Decimal("0.07"), active=True)
    benefit = Benefit(name="SYNTHETIC", benefit_type=BenefitType.EMPLOYEE, discount_percentage=50, is_active=True)
    db_session.add_all([actor, patient, service, benefit])
    db_session.flush()
    assignment = PatientBenefit(patient_id=patient.id, benefit_id=benefit.id, is_active=True, verified=True)
    encounter = Encounter(patient_id=patient.id, provenance="new")
    db_session.add_all([assignment, encounter])
    db_session.flush()
    visit = Visit(patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2099, 1, 1), confirmation_context_epoch=1)
    empty_visit = Visit(patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2099, 1, 1), confirmation_context_epoch=1)
    db_session.add_all([visit, empty_visit])
    db_session.flush()
    line = VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC", qty=3,
                        price=Decimal("0.07"), currency="UZS")
    db_session.add(line)
    db_session.flush()
    application = EncounterBenefitApplication(encounter_id=encounter.id, patient_id=patient.id,
        patient_id_snapshot=patient.id, patient_benefit_id=assignment.id, patient_benefit_id_snapshot=assignment.id,
        benefit_id=benefit.id, benefit_id_snapshot=benefit.id, approved_by_user_id=actor.id,
        approved_by_user_id_snapshot=actor.id, approved_by_role_snapshot="Admin", period_timezone="Asia/Tashkent",
        period_month=date(2099, 1, 1), period_year=2099, encounter_generation=encounter.generation,
        percentage=Decimal("50"), monthly_used_before=Decimal("0"), yearly_used_before=Decimal("0"),
        gross_total=Decimal("0.21"), benefit_total=Decimal("0.10"), net_total=Decimal("0.11"))
    db_session.add(application)
    db_session.flush()
    db_session.add(EncounterBenefitVisitSnapshot(application_id=application.id, visit_id=visit.id,
        encounter_id=encounter.id, patient_id=patient.id, visit_id_snapshot=visit.id, visit_context_epoch=1))
    db_session.add(EncounterBenefitVisitSnapshot(application_id=application.id, visit_id=empty_visit.id,
        encounter_id=encounter.id, patient_id=patient.id, visit_id_snapshot=empty_visit.id, visit_context_epoch=1))
    db_session.add(EncounterBenefitAllocation(application_id=application.id, visit_id=visit.id, visit_id_snapshot=visit.id,
        visit_service_id=line.id, visit_service_id_snapshot=line.id, service_id_snapshot=service.id, visit_context_epoch=1,
        quantity=3, unit_price=Decimal("0.07"), gross_amount=Decimal("0.21"), benefit_amount=Decimal("0.10"),
        net_amount=Decimal("0.11")))
    db_session.flush()
    invariant = PaymentInvariantService(db_session)
    quote = invariant.compute_visit_quote(visit)
    assert quote.total == Decimal("0.11")
    assert quote.currency == "UZS"
    assert dict(quote.line_totals) == {line.id: Decimal("0.11")}
    assert invariant.compute_total_cost(visit) == Decimal("0.11")
    notification = FormattingMixin()._prepare_notification_data(db_session, visit, patient)
    assert notification["total_amount"] == Decimal("0.11")
    assert notification["services"] == ["• SYNTHETIC × 3 - 0.11 сум"]
    assert invariant.compute_total_cost(empty_visit) == Decimal("0.00")
    assert invariant.compute_visit_quote(empty_visit).currency == "UZS"
    empty_visit.total_price = Decimal("0.05")
    with pytest.raises(HTTPException) as error:
        invariant.compute_total_cost(empty_visit)
    assert error.value.status_code == 409
    empty_visit.total_price = None
    with pytest.raises(HTTPException) as error:
        invariant.create_payment_for_visit(visit_id=visit.id, amount=Decimal("0.12"), method="cash", note="synthetic",
                                           current_user=actor, allow_overpayment=False, commit=False)
    assert error.value.status_code == 400
    payment = invariant.create_payment_for_visit(visit_id=visit.id, amount=Decimal("0.11"), method="cash", note="synthetic",
                                                  current_user=actor, allow_overpayment=False, commit=False)
    assert payment.amount == Decimal("0.11")
    line.price = Decimal("0.08")
    with pytest.raises(HTTPException) as error:
        invariant.compute_total_cost(visit)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException):
        FormattingMixin()._prepare_notification_data(db_session, visit, patient)
    db_session.flush()
    with pytest.raises(HTTPException) as error:
        invariant.compute_total_cost(visit)
    assert error.value.status_code == 409


def test_cashier_mark_paid_http_uses_aggregate_benefit(
    client, db_session, admin_user, admin_auth_headers, test_patient, monkeypatch,
):
    from app.api.v1.endpoints.cashier import _visits

    service = Service(code="SYNTHETIC-SSOT-HTTP", name="SYNTHETIC", price=Decimal("0.07"), active=True)
    benefit = Benefit(name="SYNTHETIC", benefit_type=BenefitType.EMPLOYEE, discount_percentage=50, is_active=True)
    db_session.add_all([service, benefit])
    db_session.flush()
    assignment = PatientBenefit(patient_id=test_patient.id, benefit_id=benefit.id, is_active=True, verified=True)
    encounter = Encounter(patient_id=test_patient.id, provenance="new")
    db_session.add_all([assignment, encounter])
    db_session.flush()
    visit = Visit(patient_id=test_patient.id, encounter_id=encounter.id, visit_date=date(2099, 1, 1),
                  status="pending_confirmation", confirmation_context_epoch=1)
    db_session.add(visit)
    db_session.flush()
    line = VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC", qty=3,
                        price=Decimal("0.07"), currency="UZS")
    db_session.add(line)
    db_session.flush()
    application = EncounterBenefitApplication(encounter_id=encounter.id, patient_id=test_patient.id,
        patient_id_snapshot=test_patient.id, patient_benefit_id=assignment.id, patient_benefit_id_snapshot=assignment.id,
        benefit_id=benefit.id, benefit_id_snapshot=benefit.id, approved_by_user_id=admin_user.id,
        approved_by_user_id_snapshot=admin_user.id, approved_by_role_snapshot="Admin", period_timezone="Asia/Tashkent",
        period_month=date(2099, 1, 1), period_year=2099, encounter_generation=encounter.generation,
        percentage=Decimal("50"), monthly_used_before=Decimal("0"), yearly_used_before=Decimal("0"),
        gross_total=Decimal("0.21"), benefit_total=Decimal("0.10"), net_total=Decimal("0.11"))
    db_session.add(application)
    db_session.flush()
    db_session.add(EncounterBenefitVisitSnapshot(application_id=application.id, visit_id=visit.id,
        encounter_id=encounter.id, patient_id=test_patient.id, visit_id_snapshot=visit.id, visit_context_epoch=1))
    db_session.add(EncounterBenefitAllocation(application_id=application.id, visit_id=visit.id, visit_id_snapshot=visit.id,
        visit_service_id=line.id, visit_service_id_snapshot=line.id, service_id_snapshot=service.id, visit_context_epoch=1,
        quantity=3, unit_price=Decimal("0.07"), gross_amount=Decimal("0.21"), benefit_amount=Decimal("0.10"),
        net_amount=Decimal("0.11")))
    db_session.commit()
    daily = client.get("/api/v1/cashier/stats/by-currency", headers=admin_auth_headers)
    assert daily.status_code == 200, daily.text
    [bucket] = daily.json()
    assert bucket["currency"] == "UZS" and bucket["pending_amount"] == "0.11"
    monkeypatch.setattr(_visits, "_emit_payment_notification", AsyncMock())
    response = client.post(f"/api/v1/cashier/visits/{visit.id}/mark-paid", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    assert db_session.query(Payment).filter_by(visit_id=visit.id).one().amount == Decimal("0.11")


def test_group_payment_snapshot_rejects_equal_and_opposite_line_changes(db_session):
    actor = User(username="synthetic-snapshot-cashier", hashed_password="!", role="Admin", is_active=True)
    patient = Patient(first_name="SYNTHETIC", last_name="Snapshot")
    service = Service(code="SYNTHETIC-SNAPSHOT-LINE", name="SYNTHETIC", price=Decimal("0.10"), active=True)
    db_session.add_all([actor, patient, service])
    db_session.flush()
    encounter = Encounter(patient_id=patient.id, provenance="new")
    db_session.add(encounter)
    db_session.flush()
    visit = Visit(patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2099, 1, 1),
                  status="pending_confirmation", confirmation_context_epoch=1)
    db_session.add(visit)
    db_session.flush()
    lines = [VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC", qty=1,
                          price=Decimal("0.10"), currency="UZS") for _ in range(2)]
    db_session.add_all(lines)
    db_session.flush()
    invariant = PaymentInvariantService(db_session)
    before = invariant.summarize_visits([visit])
    lines[0].price, lines[1].price = Decimal("0.11"), Decimal("0.09")
    db_session.flush()
    after = invariant.summarize_visits([visit])
    assert before["total_amount"] == after["total_amount"] == Decimal("0.20")
    assert before["snapshot"] != after["snapshot"]
    with pytest.raises(HTTPException) as error:
        invariant.receive_grouped_payment(visit_ids=[visit.id], amount=Decimal("0.20"), method="cash",
                                          current_user=actor, snapshot=before["snapshot"])
    assert error.value.status_code == 409
    assert db_session.query(Payment).filter_by(visit_id=visit.id).count() == 0


def test_group_summary_refuses_to_add_different_or_unknown_currencies(db_session):
    patient = Patient(first_name="SYNTHETIC", last_name="Mixed")
    service = Service(code="SYNTHETIC-MIXED-CURRENCY", name="SYNTHETIC", price=Decimal("1.00"), active=True)
    db_session.add_all([patient, service])
    db_session.flush()
    visits = [Visit(patient_id=patient.id, visit_date=date(2099, 1, 1), confirmation_context_epoch=1) for _ in range(2)]
    db_session.add_all(visits)
    db_session.flush()
    lines = [VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC", qty=1,
                          price=Decimal("1.00"), currency=currency)
             for visit, currency in zip(visits, ("UZS", "USD"), strict=True)]
    db_session.add_all(lines)
    db_session.flush()
    invariant = PaymentInvariantService(db_session)
    with pytest.raises(HTTPException) as error:
        invariant.summarize_visits(visits)
    assert error.value.status_code == 409
    lines[1].currency = None
    db_session.flush()
    with pytest.raises(HTTPException) as error:
        invariant.summarize_visits(visits)
    assert error.value.status_code == 409
    lines[1].currency = "UZS"
    db_session.flush()
    assert invariant.summarize_visits(visits)["currency"] == "UZS"
