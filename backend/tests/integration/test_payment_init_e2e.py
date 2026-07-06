"""
Focused E2E tests for online payment initialization.
Ensures /payments/init works for Click/Payme/Kaspi with valid visit_id.
"""

from decimal import Decimal

import pytest

from app.models.payment import Payment


@pytest.fixture(autouse=True)
def configured_payment_providers(monkeypatch):
    from app.core.config import get_settings
    from app.services.payment_provider_manager_factory import reset_payment_manager_for_tests

    settings = get_settings()
    monkeypatch.setattr(settings, "CLICK_ENABLED", True)
    monkeypatch.setattr(settings, "CLICK_SERVICE_ID", "test_service")
    monkeypatch.setattr(settings, "CLICK_MERCHANT_ID", "test_merchant")
    monkeypatch.setattr(settings, "CLICK_SECRET_KEY", "test_secret")
    monkeypatch.setattr(settings, "PAYME_ENABLED", True)
    monkeypatch.setattr(settings, "PAYME_MERCHANT_ID", "test_merchant")
    monkeypatch.setattr(settings, "PAYME_SECRET_KEY", "test_secret")
    monkeypatch.setattr(settings, "KASPI_ENABLED", True)
    monkeypatch.setattr(settings, "KASPI_MERCHANT_ID", "test_merchant")
    monkeypatch.setattr(settings, "KASPI_SECRET_KEY", "test_secret")
    # PAY-REAUDIT-28 P0-1: env-gate должен быть явно открыт в тестах, чтобы
    # /payments/test-init возвращал 200. Раньше gate был сломан (NameError),
    # теперь работает корректно — поэтому тест должен явно включать флаг.
    monkeypatch.setattr(settings, "ENABLE_TEST_PAYMENT_INIT", True)
    reset_payment_manager_for_tests()
    yield
    reset_payment_manager_for_tests()


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

    def test_test_init_requires_auth(self, client, test_visit, db_session):
        before_count = db_session.query(Payment).count()

        response = client.post(
            "/api/v1/payments/test-init",
            json={
                "visit_id": test_visit.id,
                "amount": 150000,
                "currency": "UZS",
                "provider": "click",
                "description": "unauth test init",
            },
        )

        assert response.status_code == 401
        assert db_session.query(Payment).count() == before_count

    def test_test_init_allows_authorized_payment_staff(
        self, client, auth_headers, test_visit, db_session
    ):
        response = client.post(
            "/api/v1/payments/test-init",
            headers=auth_headers,
            json={
                "visit_id": test_visit.id,
                "amount": 150000,
                "currency": "UZS",
                "provider": "click",
                "description": "authorized test init",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        self._assert_payment_created(db_session, data["payment_id"], "click", "UZS")

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
