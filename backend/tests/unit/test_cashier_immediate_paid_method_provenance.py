"""CSH-FE-039 (P1, follow-up audit 2026-11-02): провенанс метода прямой
кассовой команды платежа.

Дефект: ``CreatePaymentRequest``/``CreateGroupedPaymentRequest`` принимали
любую строку ``method`` и передавали её в
``PaymentInvariantService.create_payment_for_visit``, который немедленно
создаёт ``Payment(status='paid', paid_at=now)`` без подтверждения
провайдером. Кассир мог выбрать Click/PayMe в модалке (или дернуть API
напрямую) — и «проведённая» оплата попадала в учёт без доказательства
списания провайдером.

Фикс: метод прямой немедленной команды валидируется на границе DTO —
разрешены только методы с ручным документальным подтверждением кассира
(``cash``, ``card``); провайдерские (``click``/``payme``/``kaspi``) и
неизвестные методы отклоняются с 422. Провайдерские оплаты идут через
``payment_init_service`` (pending → провайдер → webhook → paid).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.cashier._helpers import (
    CASHIER_HOSTED_PROVIDER_METHODS,
    CASHIER_IMMEDIATE_PAID_METHODS,
    CreateGroupedPaymentRequest,
    CreatePaymentRequest,
)


def _single(method: str) -> None:
    CreatePaymentRequest(visit_id=1, amount=Decimal("40000"), method=method, note=None)


def _grouped(method: str) -> None:
    CreateGroupedPaymentRequest(
        visit_ids=[1, 2],
        patient_id=10,
        amount=Decimal("100000"),
        method=method,
        note=None,
    )


@pytest.mark.parametrize("method", sorted(CASHIER_IMMEDIATE_PAID_METHODS))
def test_manually_receipted_methods_pass_single(method: str) -> None:
    payload = CreatePaymentRequest(
        visit_id=1, amount=Decimal("40000"), method=method, note=None
    )
    assert payload.method == method


@pytest.mark.parametrize("method", sorted(CASHIER_IMMEDIATE_PAID_METHODS))
def test_manually_receipted_methods_pass_grouped(method: str) -> None:
    payload = CreateGroupedPaymentRequest(
        visit_ids=[1, 2],
        patient_id=10,
        amount=Decimal("100000"),
        method=method,
        note=None,
    )
    assert payload.method == method


@pytest.mark.parametrize("method", sorted(CASHIER_HOSTED_PROVIDER_METHODS))
def test_hosted_provider_methods_rejected_single(method: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        _single(method)
    message = str(excinfo.value)
    assert "провайдер" in message
    # Явное различие между «провайдерский метод» и «неизвестный метод»:
    # сообщение обязано направлять к провайдер-флоу, а не к списку cash/card.
    assert "webhook" in message


@pytest.mark.parametrize("method", sorted(CASHIER_HOSTED_PROVIDER_METHODS))
def test_hosted_provider_methods_rejected_grouped(method: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        _grouped(method)
    assert "провайдер" in str(excinfo.value)


@pytest.mark.parametrize("method", ["online", "bank_transfer", "crypto", "", "  "])
def test_unknown_methods_rejected_single(method: str) -> None:
    with pytest.raises(ValidationError):
        _single(method)


@pytest.mark.parametrize("method", ["online", "bank_transfer", "crypto"])
def test_unknown_methods_rejected_grouped(method: str) -> None:
    with pytest.raises(ValidationError):
        _grouped(method)


def test_method_is_normalized_to_canonical_lowercase() -> None:
    """Регистр/пробелы не создают второй «метод» в БД: канонизация до
    сохранения (ранее 'Cash ' прошёл бы как есть)."""
    payload = CreatePaymentRequest(
        visit_id=1, amount=Decimal("40000"), method="  Cash ", note=None
    )
    assert payload.method == "cash"


def test_default_method_remains_cash() -> None:
    payload = CreatePaymentRequest(visit_id=1, amount=Decimal("40000"))
    assert payload.method == "cash"
    grouped = CreateGroupedPaymentRequest(visit_ids=[1], amount=Decimal("40000"))
    assert grouped.method == "cash"


def test_hosted_methods_rejection_names_the_exact_method() -> None:
    """Ошибка обязана назвать конкретный метод — кассир видит, что именно
    нельзя провести напрямую."""
    with pytest.raises(ValidationError) as excinfo:
        _single("payme")
    assert "payme" in str(excinfo.value)
