"""Protected payment template contract; HTTP delivery checks use a real DB.

See tests/integration/test_telegram_notifications_private_scope.py.
"""
from app.api.v1.endpoints import telegram_notifications


def test_safe_payment_template_data_uses_configured_protected_patient_route(
    monkeypatch,
):
    monkeypatch.setattr(
        telegram_notifications.settings,
        "FRONTEND_URL",
        "https://portal.example.com/",
    )

    template_data = telegram_notifications._safe_payment_template_data(
        {
            "amount": 125000,
            "transaction_id": "txn-secret",
            "invoice_id": "invoice-secret",
            "provider_payment_id": "provider-secret",
            "receipt_link": "https://provider.example.com/receipt/txn-secret",
        }
    )

    assert template_data["receipt_link"] == (
        "https://portal.example.com/telegram/mini-app/patient?section=payments"
    )
    assert template_data["transaction_id"] == "available-in-protected-account"
    assert "txn-secret" not in str(template_data)
    assert "invoice-secret" not in str(template_data)
    assert "provider-secret" not in str(template_data)
    assert "provider.example.com" not in str(template_data)
