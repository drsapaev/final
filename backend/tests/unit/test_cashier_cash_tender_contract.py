"""CSH-FE-040 (follow-up audit 2026-11-02): кассовое подтверждение
«внесено/сдача» доходит до платёжной записи, а не теряется в сужении
payload.

Дефект: CashPaymentModal считал сдачу и передавал ``received_amount``/
``change_due`` наверх, но ``useCashierActions.processPayment`` сужал payload
до ``visit_id/amount/method/note`` — документальное подтверждение кассира
(сколько получено, сколько сдано) терялось ДО записи, и его нельзя было
показать на авторитетном чеке. Бэкенд-DTO полей не имел вовсе.

Контракт после фикса:
  * ``CreatePaymentRequest``/``CreateGroupedPaymentRequest`` принимают
    опциональные ``received_amount``/``change_due`` ТОЛЬКО для ``cash`` и
    только парой; инвариант «внесено = сумма + сдача» (422 при расхождении);
  * ``PaymentInvariantService.create_payment_for_visit`` сохраняет
    подтверждение в ``Payment.provider_data['cash_tender']`` (JSON-колонка,
    без миграции), не меняя ``amount`` — «внесено» ≠ отдельная выручка.

Red-first: на префиксном исходнике DTO не принимал эти поля (TypeError),
а сервис не имел ``cash_tender`` — оба теста падали до правки.
"""

from __future__ import annotations

import os
import tempfile
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.cashier._helpers import (
    CreateGroupedPaymentRequest,
    CreatePaymentRequest,
)
from app.db import base  # noqa: F401 — регистрация всех моделей
from app.db.base_class import Base
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.services.payment_invariant_service import PaymentInvariantService


# ────────────────────────── DTO-контракт ──────────────────────────

class TestCashTenderDtoContract:
    """Инвариант «внесено = сумма + сдача» на обоих кассовых DTO."""

    def test_single_cash_tender_accepted(self):
        req = CreatePaymentRequest(
            visit_id=1,
            amount=Decimal("100000"),
            method="cash",
            received_amount=Decimal("150000"),
            change_due=Decimal("50000"),
        )
        assert req.received_amount == Decimal("150000")
        assert req.change_due == Decimal("50000")

    def test_single_without_tender_still_valid(self):
        """Обратная совместимость: прежние клиенты без полей проходят."""
        req = CreatePaymentRequest(visit_id=1, amount=Decimal("100000"), method="cash")
        assert req.received_amount is None
        assert req.change_due is None

    def test_single_exact_tender_accepted(self):
        req = CreatePaymentRequest(
            visit_id=1,
            amount=Decimal("100000"),
            method="cash",
            received_amount=Decimal("100000"),
            change_due=Decimal("0"),
        )
        assert req.change_due == Decimal("0")

    def test_single_change_mismatch_rejected(self):
        with pytest.raises(ValidationError):
            CreatePaymentRequest(
                visit_id=1,
                amount=Decimal("100000"),
                method="cash",
                received_amount=Decimal("150000"),
                change_due=Decimal("60000"),
            )

    def test_single_underpayment_rejected(self):
        with pytest.raises(ValidationError):
            CreatePaymentRequest(
                visit_id=1,
                amount=Decimal("100000"),
                method="cash",
                received_amount=Decimal("90000"),
                change_due=Decimal("0"),
            )

    def test_single_card_tender_rejected(self):
        """Для card/provider «внесено/сдача» бессмысленны — 422."""
        with pytest.raises(ValidationError):
            CreatePaymentRequest(
                visit_id=1,
                amount=Decimal("100000"),
                method="card",
                received_amount=Decimal("150000"),
                change_due=Decimal("50000"),
            )

    def test_single_half_pair_rejected(self):
        with pytest.raises(ValidationError):
            CreatePaymentRequest(
                visit_id=1,
                amount=Decimal("100000"),
                method="cash",
                received_amount=Decimal("150000"),
            )

    def test_grouped_cash_tender_accepted(self):
        req = CreateGroupedPaymentRequest(
            visit_ids=[1, 2],
            amount=Decimal("100000"),
            method="cash",
            received_amount=Decimal("150000"),
            change_due=Decimal("50000"),
        )
        assert req.received_amount == Decimal("150000")

    def test_grouped_change_mismatch_rejected(self):
        with pytest.raises(ValidationError):
            CreateGroupedPaymentRequest(
                visit_ids=[1, 2],
                amount=Decimal("100000"),
                method="cash",
                received_amount=Decimal("150000"),
                change_due=Decimal("1"),
            )

    def test_grouped_card_tender_rejected(self):
        with pytest.raises(ValidationError):
            CreateGroupedPaymentRequest(
                visit_ids=[1, 2],
                amount=Decimal("100000"),
                method="card",
                received_amount=Decimal("150000"),
                change_due=Decimal("50000"),
            )


# ─────────────────────── Персистентность ───────────────────────

@pytest.fixture()
def fresh_engine():
    """Изолированный файловый SQLite: коммит виден НОВОЙ сессией."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()
        try:
            os.unlink(db_path)
        except OSError:
            pass


def _seed_visit(engine) -> tuple[int, int]:
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        user = User(
            username="csh040_cashier",
            email="csh040@example.com",
            full_name="Cashier CSH-040",
            hashed_password="not-a-real-hash",
            role="Cashier",
            is_active=True,
        )
        patient = Patient(last_name="Наличных", first_name="Пациент")
        session.add(user)
        session.add(patient)
        session.flush()
        visit = Visit(patient_id=patient.id, status="open")
        session.add(visit)
        session.flush()
        # Неоплаченная услуга на 100 000 — иначе сервис честно откажет
        # («все услуги уже оплачены») до создания платежа.
        from app.models.visit import VisitService

        session.add(
            VisitService(
                visit_id=visit.id,
                service_id=101,
                name="Приём (CSH-FE-040)",
                qty=1,
                price=Decimal("100000"),
                currency="UZS",
            )
        )
        session.commit()
        return visit.id, user.id


class TestCashTenderPersistence:
    def test_tender_persisted_in_provider_data(self, fresh_engine):
        """100k к оплате / 150k внесено / 50k сдача — подтверждение
        сохраняется в provider_data, amount остаётся чистой суммой."""
        visit_id, user_id = _seed_visit(fresh_engine)
        SessionLocal = sessionmaker(bind=fresh_engine)

        with SessionLocal() as session:
            service = PaymentInvariantService(session)
            payment = service.create_payment_for_visit(
                visit_id=visit_id,
                amount=Decimal("100000"),
                method="cash",
                note="CSH-FE-040 tender",
                current_user=type("U", (), {"id": user_id})(),
                cash_tender={
                    "received_amount": "150000",
                    "change_due": "50000",
                },
            )
            assert payment.id is not None

        # НОВАЯ сессия: подтверждение пережило коммит.
        with SessionLocal() as session:
            from app.models.payment import Payment

            stored = session.get(Payment, payment.id)
            assert stored is not None
            assert stored.amount == Decimal("100000"), "внесено ≠ выручка"
            assert stored.provider_data == {
                "cash_tender": {"received_amount": "150000", "change_due": "50000"}
            }

    def test_no_tender_leaves_provider_data_null(self, fresh_engine):
        visit_id, user_id = _seed_visit(fresh_engine)
        SessionLocal = sessionmaker(bind=fresh_engine)

        with SessionLocal() as session:
            service = PaymentInvariantService(session)
            payment = service.create_payment_for_visit(
                visit_id=visit_id,
                amount=Decimal("100000"),
                method="cash",
                note=None,
                current_user=type("U", (), {"id": user_id})(),
            )

        with SessionLocal() as session:
            from app.models.payment import Payment

            stored = session.get(Payment, payment.id)
            assert stored.provider_data is None
