"""Exact encounter-level benefit calculation and deterministic allocation.

This is a pure calculation. It neither selects an entitlement nor authorizes,
stores, approves or applies a benefit. Callers must supply a locked, verified
snapshot of the eligible lines, policy and remaining limits.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal


class BenefitAllocationError(ValueError):
    """A financial input cannot be represented safely or unambiguously."""


@dataclass(frozen=True)
class BenefitLine:
    line_id: int
    visit_id: int
    quantity: int
    unit_price: Decimal


@dataclass(frozen=True)
class AllocatedBenefitLine:
    line_id: int
    visit_id: int
    gross: Decimal
    discount: Decimal
    net: Decimal


@dataclass(frozen=True)
class EncounterBenefitAllocation:
    gross: Decimal
    discount: Decimal
    net: Decimal
    lines: tuple[AllocatedBenefitLine, ...]


_MAX_INTEGER = 2_147_483_647  # PostgreSQL INTEGER IDs and quantity.
_MAX_CENTS = 999_999_999_999  # Numeric(12, 2), used by invoice amounts.
_MAX_AMOUNT = Decimal("9999999999.99")
_HUNDRED = Decimal("100")
# No amount representable by Numeric(12,2) can produce half a cent from a
# percentage this small. This also avoids constructing astronomically large
# integer denominators for inputs such as Decimal('1e-1000000000').
_BELOW_HALF_CENT_PERCENT = Decimal("0.00000000005")


def _positive_integer(value: object) -> int:
    if type(value) is not int or not 1 <= value <= _MAX_INTEGER:
        raise BenefitAllocationError("invalid identifier or quantity")
    return value


def _money_cents(value: object) -> int:
    """Convert an exact Decimal to cents without context-dependent rounding."""
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise BenefitAllocationError("money must be a finite non-negative Decimal")
    if value.is_zero():
        return 0

    sign, digits, exponent = value.as_tuple()
    if sign or not isinstance(exponent, int):
        raise BenefitAllocationError("invalid monetary amount")
    shift = exponent + 2
    if shift < 0:
        trailing = -shift
        if trailing >= len(digits) or any(digits[-trailing:]):
            raise BenefitAllocationError("money must be exactly representable in cents")
        digits = digits[:-trailing]
        shift = 0

    # The column bound also makes the following integer conversion and power
    # bounded, even when the Decimal carries an enormous positive exponent.
    if len(digits) + shift > 12:
        raise BenefitAllocationError("monetary amount exceeds Numeric(12,2)")
    cents = int("".join(str(digit) for digit in digits)) * (10 ** shift)
    if cents > _MAX_CENTS:
        raise BenefitAllocationError("monetary amount exceeds Numeric(12,2)")
    return cents


def _rounded_discount_cents(gross_cents: int, percent: Decimal) -> int:
    """Round the aggregate percentage once, using exact half-even ties."""
    if gross_cents == 0 or percent <= _BELOW_HALF_CENT_PERCENT:
        return 0
    numerator, denominator = percent.as_integer_ratio()
    whole, remainder = divmod(gross_cents * numerator, denominator * 100)
    comparison = remainder * 2 - denominator * 100
    if comparison > 0 or (comparison == 0 and whole % 2):
        whole += 1
    return whole


def _cap_cents(value: object) -> int:
    """Compare a policy cap without overflowing the maximum invoice amount.

    Policy budgets can exceed Numeric(12,2). Such a cap cannot constrain a
    valid invoice, even when it has fractions below one cent; saturate only
    this internal comparison, never the caller's original policy snapshot.
    Smaller caps must be exact cents and are never rounded up.
    """
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise BenefitAllocationError("cap must be a finite non-negative Decimal")
    if value > _MAX_AMOUNT:
        return _MAX_CENTS
    return _money_cents(value)


def _decimal_cents(cents: int) -> Decimal:
    # Construct directly so an altered global Decimal context cannot round a
    # monetary value or affect its exponent.
    return Decimal((0, tuple(map(int, str(cents))), -2))


def allocate_encounter_benefit(
    lines: Iterable[BenefitLine],
    *,
    percent: Decimal,
    max_discount: Decimal | None = None,
    remaining_monthly: Decimal | None = None,
    remaining_yearly: Decimal | None = None,
) -> EncounterBenefitAllocation:
    """Calculate one discount on eligible gross and apportion exact cents.

    All monetary and percentage inputs must already be server-owned Decimals;
    binary floats are rejected. Optional caps are applied to the single
    half-even-rounded aggregate, before allocating. Each line's share uses
    the largest-remainder method, with lower line IDs breaking equal ties.
    The algorithm works per line, never per unit of quantity.
    """
    if not isinstance(percent, Decimal) or not percent.is_finite() or not Decimal(0) <= percent <= _HUNDRED:
        raise BenefitAllocationError("percentage must be a finite Decimal from 0 to 100")

    caps = [
        _cap_cents(cap)
        for cap in (max_discount, remaining_monthly, remaining_yearly)
        if cap is not None
    ]
    line_rows: list[tuple[int, int, int]] = []
    seen: set[int] = set()
    gross_cents = 0
    try:
        for line in lines:
            if not isinstance(line, BenefitLine):
                raise BenefitAllocationError("invalid line")
            line_id = _positive_integer(line.line_id)
            visit_id = _positive_integer(line.visit_id)
            qty = _positive_integer(line.quantity)
            if line_id in seen:
                raise BenefitAllocationError("duplicate line identifier")
            seen.add(line_id)
            line_gross = _money_cents(line.unit_price) * qty
            gross_cents += line_gross
            if line_gross > _MAX_CENTS or gross_cents > _MAX_CENTS:
                raise BenefitAllocationError("encounter total exceeds Numeric(12,2)")
            line_rows.append((line_id, visit_id, line_gross))
    except TypeError as exc:
        raise BenefitAllocationError("lines must be iterable") from exc
    if not line_rows:
        raise BenefitAllocationError("at least one eligible line is required")

    discount_cents = _rounded_discount_cents(gross_cents, percent)
    if caps:
        discount_cents = min(discount_cents, *caps)

    shares: dict[int, int] = {}
    if gross_cents:
        remainder_ranking: list[tuple[int, int]] = []
        for line_id, _, line_gross in line_rows:
            share, remainder = divmod(discount_cents * line_gross, gross_cents)
            shares[line_id] = share
            remainder_ranking.append((-remainder, line_id))
        unallocated = discount_cents - sum(shares.values())
        for _, line_id in sorted(remainder_ranking)[:unallocated]:
            shares[line_id] += 1

    result_lines = tuple(
        AllocatedBenefitLine(
            line_id=line_id,
            visit_id=visit_id,
            gross=_decimal_cents(line_gross),
            discount=_decimal_cents(shares.get(line_id, 0)),
            net=_decimal_cents(line_gross - shares.get(line_id, 0)),
        )
        for line_id, visit_id, line_gross in sorted(line_rows)
    )
    return EncounterBenefitAllocation(
        gross=_decimal_cents(gross_cents),
        discount=_decimal_cents(discount_cents),
        net=_decimal_cents(gross_cents - discount_cents),
        lines=result_lines,
    )
