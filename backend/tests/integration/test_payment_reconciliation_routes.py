from app.core.security import get_password_hash
from app.models.user import User


def _cashier_headers(client, db_session):
    cashier = db_session.query(User).filter(User.username == "route_cashier").first()
    if cashier is None:
        cashier = User(
            username="route_cashier",
            email="route.cashier@test.com",
            hashed_password=get_password_hash("cashier123"),
            role="Cashier",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(cashier)
        db_session.commit()
        db_session.refresh(cashier)

    response = client.post(
        "/api/v1/authentication/login",
        json={"username": cashier.username, "password": "cashier123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_reconcile_all_route_dispatches_to_all_provider_service(
    client, auth_headers, monkeypatch
):
    calls = {"all": 0, "provider": []}

    def fake_reconcile_all(self, *, start_date, end_date):
        calls["all"] += 1
        return {
            "route": "all",
            "providers": {},
            "overall_summary": {"total_discrepancies": 0},
        }

    def fake_reconcile_provider(self, *, provider, start_date, end_date):
        calls["provider"].append(provider)
        return {"route": "provider", "provider": provider}

    monkeypatch.setattr(
        "app.api.v1.endpoints.payment_reconciliation."
        "PaymentReconciliationApiService.reconcile_all_providers",
        fake_reconcile_all,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.payment_reconciliation."
        "PaymentReconciliationApiService.reconcile_provider",
        fake_reconcile_provider,
    )

    response = client.post(
        "/api/v1/payments/reconcile/all",
        params={"start_date": "2026-05-01", "end_date": "2026-05-31"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["route"] == "all"
    assert calls == {"all": 1, "provider": []}


def test_reconcile_all_route_keeps_admin_only_permission(
    client, db_session, monkeypatch
):
    def fake_reconcile_all(self, *, start_date, end_date):
        return {"route": "all"}

    def fake_reconcile_provider(self, *, provider, start_date, end_date):
        return {"route": "provider", "provider": provider}

    monkeypatch.setattr(
        "app.api.v1.endpoints.payment_reconciliation."
        "PaymentReconciliationApiService.reconcile_all_providers",
        fake_reconcile_all,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.payment_reconciliation."
        "PaymentReconciliationApiService.reconcile_provider",
        fake_reconcile_provider,
    )

    response = client.post(
        "/api/v1/payments/reconcile/all",
        params={"start_date": "2026-05-01", "end_date": "2026-05-31"},
        headers=_cashier_headers(client, db_session),
    )

    assert response.status_code == 403
