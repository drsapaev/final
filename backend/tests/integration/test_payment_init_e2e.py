"""
Focused E2E tests for online payment initialization.
Ensures /payments/init works for Click/Payme/Kaspi with valid visit_id.
"""

from decimal import Decimal

import pytest

from app.models.payment import Payment


@pytest.mark.integration
@pytest.mark.e2e
class TestPaymentInitE2E:
    def _assert_payment_created(self, db_session, payment_id, provider, currency):
        payment = db_session.query(Payment).filter(Payment.id == payment_id).first()
        assert payment is not None
        assert payment.provider == provider
        assert payment.currency == currency
        assert payment.status in ["pending", "processing"]

    def test_click_init_success(self, client, auth_headers, test_visit, db_session):
        response = client.post(
            "/api/v1/payments/init",
            headers=auth_headers,
            json={
                "visit_id": test_visit.id,
                "amount": 150000,
                "currency": "UZS",
                "provider": "click",
                "description": "Click init test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["payment_id"] is not None
        assert data["payment_url"]
        self._assert_payment_created(db_session, data["payment_id"], "click", "UZS")

    def test_payme_init_success(self, client, auth_headers, test_visit, db_session):
        response = client.post(
            "/api/v1/payments/init",
            headers=auth_headers,
            json={
                "visit_id": test_visit.id,
                "amount": 150000,
                "currency": "UZS",
                "provider": "payme",
                "description": "Payme init test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["payment_id"] is not None
        assert data["payment_url"]
        self._assert_payment_created(db_session, data["payment_id"], "payme", "UZS")

    def test_kaspi_init_success(self, client, auth_headers, test_visit, db_session):
        response = client.post(
            "/api/v1/payments/init",
            headers=auth_headers,
            json={
                "visit_id": test_visit.id,
                "amount": 1000,
                "currency": "KZT",
                "provider": "kaspi",
                "description": "Kaspi init test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["payment_id"] is not None
        assert data["payment_url"]
        self._assert_payment_created(db_session, data["payment_id"], "kaspi", "KZT")

    def test_visit_payments_list_includes_new_payment(
        self, client, auth_headers, test_visit, db_session
    ):
        # Arrange: create a payment record directly
        payment = Payment(
            visit_id=test_visit.id,
            amount=Decimal("250000.00"),
            currency="UZS",
            status="pending",
            provider="click",
        )
        db_session.add(payment)
        db_session.commit()

        response = client.get(
            f"/api/v1/payments/visit/{test_visit.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(p["payment_id"] == payment.id for p in data["payments"])
