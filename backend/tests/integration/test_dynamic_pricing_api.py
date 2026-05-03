from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.dynamic_pricing import PricingRule, PricingRuleService, ServicePackage
from app.models.service import Service


from tests.auth_test_credentials import (
    ADMIN_PASSWORD,
)

def _login_admin(client, admin_user):
    login_response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": ADMIN_PASSWORD},
    )
    assert login_response.status_code == 200, login_response.text
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


@pytest.mark.integration
def test_dynamic_pricing_rule_delete_cleans_linked_rows(
    client,
    db_session,
    admin_user,
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

    headers = _login_admin(client, admin_user)
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

