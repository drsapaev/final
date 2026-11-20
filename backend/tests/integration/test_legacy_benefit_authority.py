"""The legacy client amount cannot create a benefit application."""

import pytest

from app.models.discount_benefits import (
    Benefit,
    BenefitApplication,
    Discount,
    DiscountType,
    LoyaltyProgram,
    PatientBenefit,
)
from app.services.discount_benefits_service import (
    DiscountBenefitsService,
    EncounterBenefitAuthorityRequired,
)


@pytest.fixture
def verified_benefit(db_session, test_patient):
    benefit = Benefit(
        name="Synthetic verified benefit",
        benefit_type="employee",
        discount_percentage=25,
        is_active=True,
    )
    assignment = PatientBenefit(
        patient_id=test_patient.id,
        benefit=benefit,
        is_active=True,
        verified=True,
        monthly_used_amount=17,
        yearly_used_amount=23,
    )
    db_session.add(assignment)
    db_session.commit()
    return assignment


def test_service_rejects_legacy_amount_without_mutating_ledger(
    db_session, verified_benefit, test_visit
):
    before = db_session.query(BenefitApplication).count()
    service = DiscountBenefitsService(db_session)
    for amount in (100.0, 1000000.0):
        with pytest.raises(EncounterBenefitAuthorityRequired):
            service.apply_benefit(
                patient_benefit_id=verified_benefit.id,
                amount=amount,
                visit_id=test_visit.id,
            )
    db_session.refresh(verified_benefit)
    assert db_session.query(BenefitApplication).count() == before
    assert verified_benefit.monthly_used_amount == 17
    assert verified_benefit.yearly_used_amount == 23
    assert verified_benefit.last_used_date is None


def test_regular_discount_and_loyalty_still_work(db_session, test_patient, test_visit):
    discount = Discount(name="Synthetic discount", discount_type=DiscountType.PERCENTAGE, value=10)
    program = LoyaltyProgram(
        name="Synthetic points",
        points_per_ruble=1,
        min_purchase_for_points=0,
        ruble_per_point=1,
        min_points_to_redeem=1,
        is_active=True,
    )
    db_session.add_all([discount, program])
    db_session.commit()
    service = DiscountBenefitsService(db_session)
    result = service.apply_discount(discount.id, 100, visit_id=test_visit.id)
    assert result.discount_amount == 10
    assert service.earn_loyalty_points(test_patient.id, program.id, 100, visit_id=test_visit.id) == 100
    assert service.get_patient_loyalty_balance(test_patient.id, program.id) == 100
    preview = service.calculate_total_discount(test_patient.id, [], 100)
    assert preview['benefits'] == []
    assert preview['total_discount'] == 10
    assert preview['final_amount'] == 90
    assert preview['loyalty_points_available'] == 90


def test_legacy_preview_requires_encounter_for_verified_benefit(
    client, db_session, verified_benefit, test_patient, auth_headers
):
    service = DiscountBenefitsService(db_session)
    with pytest.raises(EncounterBenefitAuthorityRequired):
        service.calculate_total_discount(test_patient.id, [], 100)
    response = client.post(
        "/api/v1/discount-benefits/calculate-discount",
        headers=auth_headers,
        json={"patient_id": test_patient.id, "service_ids": [], "amount": 100},
    )
    assert response.status_code == 409
    assert db_session.query(BenefitApplication).count() == 0
    db_session.refresh(verified_benefit)
    assert verified_benefit.monthly_used_amount == 17
    assert verified_benefit.yearly_used_amount == 23


def test_admin_legacy_application_is_unavailable_and_patient_is_forbidden(
    client, db_session, verified_benefit, test_visit, auth_headers, patient_token
):
    before = db_session.query(BenefitApplication).count()
    payload = {
        "patient_benefit_id": verified_benefit.id,
        "visit_id": test_visit.id,
        "amount": 100,
    }
    for _ in range(2):
        response = client.post(
            "/api/v1/discount-benefits/benefits/apply",
            headers=auth_headers,
            json=payload,
        )
        assert response.status_code == 409
    response = client.post(
        "/api/v1/discount-benefits/benefits/apply",
        headers={"Authorization": f"Bearer {patient_token}"},
        json=payload,
    )
    assert response.status_code == 403
    db_session.refresh(verified_benefit)
    assert db_session.query(BenefitApplication).count() == before
    assert verified_benefit.monthly_used_amount == 17
    assert verified_benefit.yearly_used_amount == 23
