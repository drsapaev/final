"""Exact, deterministic allocation of one benefit across an encounter.

These tests exercise the arithmetic contract only. They do not claim to
verify clinical eligibility, administrator approval, quotas under concurrency,
or the persisted payment ledger.
"""
from __future__ import annotations

import random
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal, localcontext

import pytest

from app.services.encounter_benefit_allocation import (
    BenefitAllocationError,
    BenefitLine,
    allocate_encounter_benefit,
)

D = Decimal
CENT = D("0.01")


def line(line_id, visit_id, quantity, unit_price):
    return BenefitLine(line_id=line_id, visit_id=visit_id, quantity=quantity, unit_price=unit_price)


def test_percentage_is_rounded_once_across_visits_not_per_line_or_unit():
    result = allocate_encounter_benefit(
        [line(20, 2, 2, D("0.02")), line(10, 1, 3, D("0.01"))],
        percent=D("50"),
    )
    assert (result.gross, result.discount, result.net) == (D("0.07"), D("0.04"), D("0.03"))
    assert [(item.line_id, item.visit_id, item.gross, item.discount, item.net) for item in result.lines] == [
        (10, 1, D("0.03"), D("0.02"), D("0.01")),
        (20, 2, D("0.04"), D("0.02"), D("0.02")),
    ]


@pytest.mark.parametrize(
    ("gross", "expected"),
    [("0.01", "0.00"), ("0.03", "0.02"), ("0.05", "0.02"), ("0.07", "0.04")],
)
def test_aggregate_ties_use_half_even_rounding(gross, expected):
    result = allocate_encounter_benefit([line(1, 1, 1, D(gross))], percent=D("50"))
    assert result.discount == D(expected)
    assert result.gross == result.discount + result.net


@pytest.mark.parametrize(("percentage", "expected"), [("33.5", "1.00"), ("34.5", "1.04")])
def test_fractional_percentage_uses_the_same_exact_half_even_policy(percentage, expected):
    result = allocate_encounter_benefit([line(1, 1, 3, D("1.00"))], percent=D(percentage))
    assert result.discount == D(expected)


def test_largest_remainder_ties_use_line_id_not_input_order():
    inputs = [line(30, 2, 1, D("0.01")), line(10, 1, 1, D("0.01")), line(20, 2, 1, D("0.01"))]
    first = allocate_encounter_benefit(inputs, percent=D("50"))
    reversed_result = allocate_encounter_benefit(list(reversed(inputs)), percent=D("50"))
    assert first == reversed_result
    assert [(item.line_id, item.discount) for item in first.lines] == [
        (10, D("0.01")), (20, D("0.01")), (30, D("0.00")),
    ]
    assert first.discount == D("0.02")


def test_qty_above_one_uses_aggregate_discount_not_equal_unit_rounding():
    result = allocate_encounter_benefit(
        [line(7, 3, 3, D("1.00"))], percent=D("100"), max_discount=D("1.00")
    )
    assert (result.gross, result.discount, result.net) == (D("3.00"), D("1.00"), D("2.00"))
    assert result.lines[0].gross == D("3.00")
    assert result.lines[0].discount == D("1.00")
    assert result.lines[0].net == D("2.00")


def test_maximum_and_remaining_period_budgets_apply_to_aggregate_once():
    result = allocate_encounter_benefit(
        [line(1, 11, 2, D("20.00")), line(2, 12, 3, D("20.00"))],
        percent=D("80"), max_discount=D("40.00"),
        remaining_monthly=D("20.00"), remaining_yearly=D("30.00"),
    )
    assert (result.gross, result.discount, result.net) == (D("100.00"), D("20.00"), D("80.00"))
    assert [(item.line_id, item.discount) for item in result.lines] == [(1, D("8.00")), (2, D("12.00"))]


@pytest.mark.parametrize("budget_name", ["max_discount", "remaining_monthly", "remaining_yearly"])
def test_zero_budget_limits_discount_to_zero(budget_name):
    result = allocate_encounter_benefit(
        [line(1, 1, 1, D("9.99"))], percent=D("100"), **{budget_name: D("0.00")}
    )
    assert (result.gross, result.discount, result.net) == (D("9.99"), D("0.00"), D("9.99"))


def test_zero_price_and_zero_percentage_are_valid():
    zero_price = allocate_encounter_benefit(
        [line(3, 2, 4, D("0.00"))], percent=D("100")
    )
    assert (zero_price.gross, zero_price.discount, zero_price.net) == (D("0.00"),) * 3
    assert zero_price.lines[0].discount == D("0.00")
    zero_rate = allocate_encounter_benefit(
        [line(1, 1, 3, D("1.00"))], percent=D("0")
    )
    assert (zero_rate.gross, zero_rate.discount, zero_rate.net) == (D("3.00"), D("0.00"), D("3.00"))


def test_full_discount_never_exceeds_line_gross():
    result = allocate_encounter_benefit(
        [line(11, 1, 2, D("1.23")), line(12, 2, 3, D("0.02")), line(13, 2, 2, D("0.00"))],
        percent=D("100"),
    )
    assert result.discount == result.gross == D("2.52")
    assert result.net == D("0.00")
    assert all(item.discount == item.gross and item.net == 0 for item in result.lines)


def test_large_quantity_is_computed_without_per_unit_expansion():
    result = allocate_encounter_benefit(
        [line(1, 1, 2147483647, D("0.01"))], percent=D("50")
    )
    assert (result.gross, result.discount, result.net) == (
        D("21474836.47"), D("10737418.24"), D("10737418.23")
    )


def test_numeric_maximum_is_preserved_exactly():
    result = allocate_encounter_benefit(
        [line(1, 1, 1, D("9999999999.99"))], percent=D("100")
    )
    assert result.gross == result.discount == D("9999999999.99")
    assert result.net == D("0.00")


def test_calculation_does_not_depend_on_ambient_decimal_context():
    inputs = [line(8, 1, 3, D("1234.56")), line(9, 2, 7, D("987.65"))]
    expected = allocate_encounter_benefit(inputs, percent=D("33.33"), remaining_monthly=D("9999.99"))
    with localcontext() as context:
        context.prec = 5
        context.rounding = ROUND_DOWN
        observed = allocate_encounter_benefit(inputs, percent=D("33.33"), remaining_monthly=D("9999.99"))
    assert observed == expected


def test_tiny_nonzero_percent_rounds_to_zero_without_enormous_integer_conversion():
    result = allocate_encounter_benefit(
        [line(1, 1, 1, D("9999999999.99"))], percent=D("1E-1000000000")
    )
    assert result.discount == D("0.00")
    assert result.net == D("9999999999.99")


@pytest.mark.parametrize(
    ("percentage", "expected"),
    [("0.00000000005", "0.00"), ("0.00000000005000000001", "0.01")],
)
def test_small_percentage_shortcut_has_an_exact_half_cent_boundary(percentage, expected):
    result = allocate_encounter_benefit(
        [line(1, 1, 1, D("9999999999.99"))], percent=D(percentage)
    )
    assert result.discount == D(expected)


@pytest.mark.parametrize("price", [D("1E-1000000000"), D("1E+1000000000")])
def test_extreme_nonzero_unit_price_is_rejected_without_unbounded_expansion(price):
    with pytest.raises(BenefitAllocationError):
        allocate_encounter_benefit([line(1, 1, 1, price)], percent=D("50"))


@pytest.mark.parametrize("zero", [D("0E-1000000000"), D("0E+1000000000"), D("-0E-1000000000")])
def test_decimal_zero_with_extreme_exponent_is_still_valid(zero):
    result = allocate_encounter_benefit(
        [line(1, 1, 1, zero)], percent=D("0"), max_discount=zero
    )
    assert (result.gross, result.discount, result.net) == (D("0.00"),) * 3


def test_empty_and_duplicate_line_ids_are_rejected():
    with pytest.raises(BenefitAllocationError):
        allocate_encounter_benefit([], percent=D("50"))
    with pytest.raises(BenefitAllocationError):
        allocate_encounter_benefit(
            [line(7, 1, 1, D("1.00")), line(7, 2, 1, D("2.00"))], percent=D("50")
        )


@pytest.mark.parametrize("quantity", [0, -1, 2147483648, True, 1.0, D("1"), "1", None])
def test_invalid_quantity_is_rejected(quantity):
    with pytest.raises(BenefitAllocationError):
        allocate_encounter_benefit([line(1, 1, quantity, D("1.00"))], percent=D("50"))


@pytest.mark.parametrize("bad_id", [0, -1, 2147483648, True, 1.0, D("1"), "1", None])
@pytest.mark.parametrize("field", ["line_id", "visit_id"])
def test_invalid_identifiers_are_rejected(field, bad_id):
    kwargs = {"line_id": 1, "visit_id": 1, "quantity": 1, "unit_price": D("1.00")}
    kwargs[field] = bad_id
    with pytest.raises(BenefitAllocationError):
        allocate_encounter_benefit([BenefitLine(**kwargs)], percent=D("50"))


@pytest.mark.parametrize(
    "price", [D("-0.01"), D("0.001"), D("NaN"), D("sNaN"), D("Infinity"), D("-Infinity"),
              D("10000000000.00"), 1.0, True, "1.00", None],
)
def test_invalid_unit_prices_are_rejected(price):
    with pytest.raises(BenefitAllocationError):
        allocate_encounter_benefit([line(1, 1, 1, price)], percent=D("50"))


@pytest.mark.parametrize("percentage", [D("-0.01"), D("100.01"), D("NaN"), D("sNaN"), D("Infinity"),
                                        D("-Infinity"), 50.0, True, "50", None])
def test_invalid_percentage_is_rejected(percentage):
    with pytest.raises(BenefitAllocationError):
        allocate_encounter_benefit([line(1, 1, 1, D("1.00"))], percent=percentage)


@pytest.mark.parametrize("budget_name", ["max_discount", "remaining_monthly", "remaining_yearly"])
@pytest.mark.parametrize("budget", [D("-0.01"), D("0.001"), D("NaN"), D("Infinity"), 1.0, True, "1.00"])
def test_invalid_budget_is_rejected_even_when_percentage_is_zero(budget_name, budget):
    with pytest.raises(BenefitAllocationError):
        allocate_encounter_benefit(
            [line(1, 1, 1, D("1.00"))], percent=D("0"), **{budget_name: budget}
        )


@pytest.mark.parametrize("budget_name", ["max_discount", "remaining_monthly", "remaining_yearly"])
@pytest.mark.parametrize(
    "budget", [D("9999999999.99"), D("10000000000.00"), D("10000000000.001"), D("1E+1000000000")]
)
def test_budget_at_or_above_maximum_does_not_constrain_valid_encounter(budget_name, budget):
    lines = [line(1, 1, 3, D("1234.56")), line(2, 2, 2, D("987.65"))]
    expected = allocate_encounter_benefit(lines, percent=D("50"))
    with localcontext() as context:
        context.prec = 5
        context.rounding = ROUND_DOWN
        result = allocate_encounter_benefit(lines, percent=D("50"), **{budget_name: budget})
    assert result == expected


@pytest.mark.parametrize("budget_name", ["max_discount", "remaining_monthly", "remaining_yearly"])
def test_non_cent_budget_below_maximum_is_rejected(budget_name):
    with pytest.raises(BenefitAllocationError):
        allocate_encounter_benefit(
            [line(1, 1, 1, D("1.00"))], percent=D("50"), **{budget_name: D("9999999999.989")}
        )


@pytest.mark.parametrize("lines", [
    [line(1, 1, 2, D("9999999999.99"))],
    [line(1, 1, 1, D("9999999999.99")), line(2, 2, 1, D("0.01"))],
])
def test_aggregate_and_line_gross_overflow_rejected(lines):
    with pytest.raises(BenefitAllocationError):
        allocate_encounter_benefit(lines, percent=D("0"))


def test_deterministic_randomized_allocation_invariants():
    rng = random.Random(4081)
    for _ in range(120):
        lines = [
            line(index + 1, 1 + rng.randrange(4), 1 + rng.randrange(15), D(rng.randrange(10001)) / 100)
            for index in range(1 + rng.randrange(8))
        ]
        percentage = D(rng.randrange(101))
        gross = sum((item.unit_price * item.quantity for item in lines), D("0.00"))
        budget = D(rng.randrange(100001)) / 100
        expected_discount = min((gross * percentage / 100).quantize(CENT, rounding=ROUND_HALF_EVEN), budget)
        result = allocate_encounter_benefit(lines, percent=percentage, remaining_monthly=budget)
        assert result.gross == gross
        assert result.discount == expected_discount
        assert result.net == gross - expected_discount
        assert sum((item.discount for item in result.lines), D("0.00")) == expected_discount
        assert sum((item.net for item in result.lines), D("0.00")) == result.net
        assert [item.line_id for item in result.lines] == sorted(item.line_id for item in lines)
        assert all(item.gross == item.discount + item.net and 0 <= item.discount <= item.gross for item in result.lines)
        assert all(item.discount == item.discount.quantize(CENT) for item in result.lines)
        assert allocate_encounter_benefit(list(reversed(lines)), percent=percentage, remaining_monthly=budget) == result
