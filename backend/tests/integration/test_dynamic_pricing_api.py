from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.appointment import Appointment
from app.models.dynamic_pricing import (
    PackagePurchase,
    PricingRule,
    PricingRuleService,
    ServicePackage,
)
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit


def _login_admin(client, admin_user, admin_password):
    login_response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": admin_password},
    )
    assert login_response.status_code == 200, login_response.text
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


@pytest.mark.integration
def test_dynamic_pricing_rule_delete_cleans_linked_rows(
    client,
    db_session,
    admin_user,
    admin_password,
):
    service = Service(
        code="DP-DEL-001",
        service_code="DP-DEL-001",
        name="Dynamic Pricing Delete Smoke Service",
        price=Decimal("10000"),
        currency="UZS",
        active=True,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    headers = _login_admin(client, admin_user, admin_password)
    create_response = client.post(
        "/api/v1/dynamic-pricing/pricing-rules",
        json={
            "name": "Dynamic Pricing Delete Smoke Rule",
            "description": "QA smoke rule",
            "rule_type": "dynamic",
            "discount_type": "percentage",
            "discount_value": 10,
            "min_quantity": 1,
            "priority": 0,
            "service_ids": [service.id],
        },
        headers=headers,
    )

    assert create_response.status_code == 200, create_response.text
    rule = create_response.json()
    rule_id = rule["id"]

    package = ServicePackage(
        name="Dynamic Pricing Delete Smoke Package",
        package_price=Decimal("9000"),
        original_price=Decimal("10000"),
        savings_amount=Decimal("1000"),
        savings_percentage=10,
        pricing_rule_id=rule_id,
    )
    db_session.add(package)
    db_session.commit()
    db_session.refresh(package)

    delete_response = client.delete(
        f"/api/v1/dynamic-pricing/pricing-rules/{rule_id}",
        headers=headers,
    )

    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["message"] == "Правило удалено"

    db_session.expire_all()
    assert db_session.query(PricingRule).filter(PricingRule.id == rule_id).first() is None
    assert (
        db_session.query(PricingRuleService)
        .filter(PricingRuleService.rule_id == rule_id)
        .count()
        == 0
    )

    refreshed_package = (
        db_session.query(ServicePackage).filter(ServicePackage.id == package.id).first()
    )
    assert refreshed_package is not None
    assert refreshed_package.pricing_rule_id is None

    db_session.delete(refreshed_package)
    db_session.delete(service)
    db_session.commit()


@pytest.mark.integration
def test_admin_can_list_dynamic_pricing_rules(client, admin_user, admin_password):
    headers = _login_admin(client, admin_user, admin_password)

    response = client.get("/api/v1/dynamic-pricing/pricing-rules", headers=headers)

    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


@pytest.mark.integration
def test_patient_cannot_create_dynamic_pricing_rule(
    client,
    db_session,
    patient_token,
):
    service = Service(
        code="DP-RBAC-001",
        service_code="DP-RBAC-001",
        name="Dynamic Pricing RBAC Service",
        price=Decimal("10000"),
        currency="UZS",
        active=True,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    before_count = db_session.query(PricingRule).count()

    response = client.post(
        "/api/v1/dynamic-pricing/pricing-rules",
        json={
            "name": "Patient Dynamic Pricing Rule",
            "description": "should be rejected",
            "rule_type": "dynamic",
            "discount_type": "percentage",
            "discount_value": 99,
            "min_quantity": 1,
            "priority": 0,
            "service_ids": [service.id],
        },
        headers={"Authorization": f"Bearer {patient_token}"},
    )

    assert response.status_code == 403
    assert db_session.query(PricingRule).count() == before_count

    db_session.delete(service)
    db_session.commit()


@pytest.mark.integration
def test_patient_cannot_read_dynamic_pricing_analytics(client, patient_token):
    response = client.get(
        "/api/v1/dynamic-pricing/pricing-analytics",
        headers={"Authorization": f"Bearer {patient_token}"},
    )

    assert response.status_code == 403


@pytest.mark.integration
def test_purchase_package_rejects_cross_patient_visit_and_appointment(
    client,
    db_session,
    admin_user,
    admin_password,
):
    purchase_patient = Patient(
        first_name="Package",
        last_name="Owner",
        phone="+998901110001",
    )
    other_patient = Patient(
        first_name="Other",
        last_name="Context",
        phone="+998901110002",
    )
    db_session.add_all([purchase_patient, other_patient])
    db_session.flush()

    other_visit = Visit(patient_id=other_patient.id, status="open")
    other_appointment = Appointment(
        patient_id=other_patient.id,
        appointment_date=date.today(),
        appointment_time="10:00",
        status="scheduled",
    )
    package = ServicePackage(
        name="Cross Patient Guard Package",
        package_price=Decimal("9000"),
        original_price=Decimal("10000"),
        savings_amount=Decimal("1000"),
        savings_percentage=10,
        is_active=True,
    )
    db_session.add_all([other_visit, other_appointment, package])
    db_session.commit()
    db_session.refresh(purchase_patient)
    db_session.refresh(other_visit)
    db_session.refresh(other_appointment)
    db_session.refresh(package)

    headers = _login_admin(client, admin_user, admin_password)

    visit_response = client.post(
        "/api/v1/dynamic-pricing/purchase-package",
        json={
            "package_id": package.id,
            "patient_id": purchase_patient.id,
            "visit_id": other_visit.id,
        },
        headers=headers,
    )
    appointment_response = client.post(
        "/api/v1/dynamic-pricing/purchase-package",
        json={
            "package_id": package.id,
            "patient_id": purchase_patient.id,
            "appointment_id": other_appointment.id,
        },
        headers=headers,
    )

    assert visit_response.status_code == 400, visit_response.text
    assert appointment_response.status_code == 400, appointment_response.text
    assert (
        db_session.query(PackagePurchase)
        .filter(PackagePurchase.patient_id == purchase_patient.id)
        .count()
        == 0
    )

