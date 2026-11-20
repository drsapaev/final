"""Canonical visit totals preserve an actual zero-valued service row."""
from decimal import Decimal, localcontext
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.payment_invariant_service import PaymentInvariantService


def _visit(lines, **legacy):
    return SimpleNamespace(services=lines, **legacy)


def _line(price, qty=1):
    return SimpleNamespace(price=price, qty=qty)


def test_zero_service_lines_override_nonzero_legacy_fields():
    visit = _visit([_line(Decimal("0.00"), 3)], total_price=Decimal("100.00"), total_amount=Decimal("200.00"))
    assert PaymentInvariantService._compute_unadjusted_total(visit) == Decimal("0.00")


def test_positive_lines_use_exact_price_times_quantity():
    visit = _visit([_line(Decimal("0.07"), 3), _line(Decimal("0.01"), 2)], total_price=Decimal("999.00"))
    assert PaymentInvariantService._compute_unadjusted_total(visit) == Decimal("0.23")


def test_unadjusted_total_does_not_inherit_low_decimal_precision():
    visit = _visit([_line(Decimal("0.07"), 3), _line(Decimal("0.01"), 2)])
    with localcontext() as context:
        context.prec = 1
        assert PaymentInvariantService._compute_unadjusted_total(visit) == Decimal("0.23")


@pytest.mark.parametrize("visit,expected", [
    (_visit([], total_price=Decimal("12.34"), total_amount=Decimal("44.00")), Decimal("12.34")),
    (_visit([], total_price=Decimal("0.00"), total_amount=Decimal("44.00")), Decimal("44.00")),
    (_visit([], total_price=None, total_amount=Decimal("44.00")), Decimal("44.00")),
    (_visit([]), Decimal("0.00")),
    (SimpleNamespace(total_price=Decimal("10.00")), Decimal("10.00")),
])
def test_legacy_amount_only_used_when_no_service_rows(visit, expected):
    assert PaymentInvariantService._compute_unadjusted_total(visit) == expected


@pytest.mark.parametrize("price", [None, Decimal("-0.01"), Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal("0.001"), "not-money", True])
def test_invalid_price_never_becomes_zero_or_legacy_total(price):
    visit = _visit([_line(price)], total_price=Decimal("1.00"))
    with pytest.raises(HTTPException) as error:
        PaymentInvariantService._compute_unadjusted_total(visit)
    assert error.value.status_code == 409


@pytest.mark.parametrize("quantity", [None, 0, -1, True, 1.5, "2", 2147483648])
def test_invalid_quantity_is_rejected(quantity):
    visit = _visit([_line(Decimal("1.00"), quantity)])
    with pytest.raises(HTTPException) as error:
        PaymentInvariantService._compute_unadjusted_total(visit)
    assert error.value.status_code == 409


@pytest.mark.parametrize("lines", [
    [_line(Decimal("6000000000.00"), 2)],
    [_line(Decimal("9999999999.99")), _line(Decimal("0.01"))],
])
def test_total_overflow_is_rejected(lines):
    with pytest.raises(HTTPException) as error:
        PaymentInvariantService._compute_unadjusted_total(_visit(lines))
    assert error.value.status_code == 409


def test_maximum_representable_total_is_accepted():
    assert PaymentInvariantService._compute_unadjusted_total(
        _visit([_line(Decimal("9999999999.99"))])
    ) == Decimal("9999999999.99")


@pytest.mark.parametrize("legacy", [Decimal("-0.01"), Decimal("NaN"), Decimal("Infinity"), Decimal("0.001"), "bad-money"])
def test_invalid_legacy_fallback_is_rejected(legacy):
    with pytest.raises(HTTPException) as error:
        PaymentInvariantService._compute_unadjusted_total(_visit([], total_price=legacy))
    assert error.value.status_code == 409
