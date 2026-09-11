from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.enums import PaymentStatus
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.user import User
from app.models.visit import VisitService
from app.services import payment_invoice_service as payment_invoice_service_module
from app.services.authentication_service import authentication_service


class _PaymentManagerStub:
    def get_provider_info(self):
        return {"click": {"supported_currencies": ["UZS"]}}

    def supports_registrar_invoice_payment(self, provider_name: str) -> bool:
        return provider_name.lower() == "click"


def test_registrar_can_create_and_list_payment_invoices(
    client: TestClient,
    registrar_auth_headers: dict[str, str],
    test_patient,
) -> None:
    create_response = client.post(
        "/api/v1/payments/invoice/create",
        headers=registrar_auth_headers,
        json={
            "amount": 100000,
            "currency": "UZS",
            "provider": "click",
            "description": "registrar payment invoice",
            "patient_info": {"id": test_patient.id},
        },
    )
    list_response = client.get(
        "/api/v1/payments/invoices/pending",
        headers=registrar_auth_headers,
    )

    assert create_response.status_code == 200
    assert create_response.json()["amount"] == 100000.0
    assert list_response.status_code == 200
    assert any(
        invoice["invoice_id"] == create_response.json()["invoice_id"]
        for invoice in list_response.json()
    )


def test_registrar_can_list_linked_cart_invoice_without_bound_provider(
    client: TestClient,
    db_session: Session,
    registrar_auth_headers: dict[str, str],
    test_visit,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        payment_invoice_service_module,
        "get_payment_manager",
        lambda: _PaymentManagerStub(),
    )
    db_session.add(
        VisitService(
            visit_id=test_visit.id,
            service_id=1,
            name="SYNTHETIC-linked cart invoice",
            qty=1,
            price=75_000,
        )
    )
    invoice = PaymentInvoice(
        patient_id=test_visit.patient_id,
        total_amount=75_000,
        currency="UZS",
        provider=None,
        status=PaymentStatus.PENDING.value,
        payment_method="cash",
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=invoice.id,
            visit_id=test_visit.id,
            visit_amount=75_000,
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/payments/invoices/pending",
        headers=registrar_auth_headers,
    )

    assert response.status_code == 200, response.text
    result = next(
        row for row in response.json() if row["invoice_id"] == invoice.id
    )
    assert result["provider"] is None
    assert result["paid_amount"] == 0
    assert result["remaining_amount"] == 75_000
    assert result["available_actions"] == [
        {"action": "start_online_payment", "provider": "click"}
    ]


def test_cashier_list_does_not_advertise_registrar_invoice_checkout(
    client: TestClient,
    db_session: Session,
    test_visit,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        payment_invoice_service_module,
        "get_payment_manager",
        lambda: _PaymentManagerStub(),
    )
    cashier = User(
        username="synthetic_invoice_cashier",
        email="synthetic-invoice-cashier@example.invalid",
        full_name="SYNTHETIC Invoice Cashier",
        hashed_password=get_password_hash("synthetic-test-password"),
        role="Cashier",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(cashier)
    db_session.add(
        VisitService(
            visit_id=test_visit.id,
            service_id=1,
            name="SYNTHETIC-cashier role invoice",
            qty=1,
            price=55_000,
        )
    )
    invoice = PaymentInvoice(
        patient_id=test_visit.patient_id,
        total_amount=55_000,
        currency="UZS",
        provider=None,
        status=PaymentStatus.PENDING.value,
        payment_method="cash",
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=invoice.id,
            visit_id=test_visit.id,
            visit_amount=55_000,
        )
    )
    db_session.commit()
    token = authentication_service.create_access_token(
        {
            "sub": str(cashier.id),
            "username": cashier.username,
            "role": cashier.role,
            "is_active": cashier.is_active,
            "is_superuser": cashier.is_superuser,
        }
    )

    response = client.get(
        "/api/v1/payments/invoices/pending",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    result = next(
        row for row in response.json() if row["invoice_id"] == invoice.id
    )
    assert result["remaining_amount"] == 55_000
    assert result["available_actions"] == []
    assert result["online_payment_block_reason"] == "role_not_allowed"


def test_registrar_cannot_create_payment_invoice_without_patient(
    client: TestClient,
    db_session: Session,
    registrar_auth_headers: dict[str, str],
) -> None:
    before_count = db_session.query(PaymentInvoice).count()

    response = client.post(
        "/api/v1/payments/invoice/create",
        headers=registrar_auth_headers,
        json={
            "amount": 100000,
            "currency": "UZS",
            "provider": "click",
            "description": "orphan invoice",
        },
    )

    assert response.status_code == 422
    assert db_session.query(PaymentInvoice).count() == before_count


def test_registrar_cannot_create_payment_invoice_for_unknown_patient(
    client: TestClient,
    db_session: Session,
    registrar_auth_headers: dict[str, str],
) -> None:
    before_count = db_session.query(PaymentInvoice).count()

    response = client.post(
        "/api/v1/payments/invoice/create",
        headers=registrar_auth_headers,
        json={
            "amount": 100000,
            "currency": "UZS",
            "provider": "click",
            "description": "unknown patient invoice",
            "patient_info": {"patient_id": 999999999},
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Пациент не найден"}
    assert db_session.query(PaymentInvoice).count() == before_count


def test_patient_cannot_create_payment_invoice_for_arbitrary_patient(
    client: TestClient,
    db_session: Session,
    patient_token: str,
) -> None:
    before_count = db_session.query(PaymentInvoice).count()

    response = client.post(
        "/api/v1/payments/invoice/create",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={
            "amount": 250000,
            "currency": "UZS",
            "provider": "click",
            "description": "patient should not create invoice",
            "patient_info": {"patient_id": 999999},
        },
    )

    assert response.status_code == 403
    assert db_session.query(PaymentInvoice).count() == before_count


def test_patient_cannot_list_pending_payment_invoices(
    client: TestClient,
    db_session: Session,
    patient_token: str,
) -> None:
    db_session.add(
        PaymentInvoice(
            patient_id=12345,
            total_amount=Decimal("50000.00"),
            currency="UZS",
            provider="click",
            status=PaymentStatus.PENDING.value,
            payment_method="click",
            notes="pending invoice not visible to patient role",
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/payments/invoices/pending",
        headers={"Authorization": f"Bearer {patient_token}"},
    )

    assert response.status_code == 403
