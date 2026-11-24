"""Building blocks for the future encounter-benefit authority.

No public authority or benefit writer exists here yet. User/Patient/Visit and
financial writers must first share a proven locking protocol; the 0108 quota
anchor and 0106 records alone do not establish that protocol.
"""

from calendar import isleap
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import isfinite

from app.services.encounter_benefit_allocation import (
    BenefitAllocationError,
    _money_cents,
)


def _age_on(born: date, on: date) -> int:
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def age_condition_satisfied(
    birth_date: date | None,
    *,
    on: date,
    age_min: int | None,
    age_max: int | None,
    date_precision_verified: bool,
) -> bool:
    """Evaluate age only after a trusted, audited exact-date verification.

    Current Patient rows do not record reliable date provenance. This pure
    helper has no authority to verify it: the future writer must derive this
    flag from locked, auditable evidence, never from a request. Until that
    workflow exists, age-based benefits remain unavailable. The decision date
    must be the clinic-local date captured for the approval, not a client date.
    """
    if type(on) is not date:
        return False
    for bound in (age_min, age_max):
        if bound is not None and (type(bound) is not int or bound < 0):
            return False
    if age_min is not None and age_max is not None and age_min > age_max:
        return False
    if age_min is None and age_max is None:
        return True
    if date_precision_verified is not True:
        return False
    if type(birth_date) is not date or birth_date > on:
        return False
    youngest = oldest = _age_on(birth_date, on)
    # In non-leap years the policy for a Feb 29 birthday on Feb 28 is not
    # encoded in the current model. Both interpretations must pass.
    if (
        (birth_date.month, birth_date.day) == (2, 29)
        and (on.month, on.day) == (2, 28)
        and not isleap(on.year)
    ):
        oldest += 1
    return (age_min is None or youngest >= age_min) and (age_max is None or oldest <= age_max)


@dataclass(frozen=True)
class BenefitUsageEvidence:
    """One prior application, already selected for the same patient/benefit.

    Historical timestamps are deliberately not accepted here: old naive
    timestamps do not identify a clinic-local period. A legacy row is charged
    to both periods until an audited reconciliation supplies trustworthy data.
    """

    amount: Decimal | float
    legacy: bool
    period_month: date | None = None
    period_timezone: str | None = None


@dataclass(frozen=True)
class BenefitQuotaUsage:
    monthly_used: Decimal
    yearly_used: Decimal


def _legacy_cents(value: object) -> int:
    # Historical DB Float is binary. Its exact stored value can be slightly
    # above a cent boundary; ceiling never silently releases quota. An admin
    # reconciliation can resolve disputed historic data separately.
    if type(value) is not float or not isfinite(value) or value < 0:
        raise BenefitAllocationError("invalid legacy benefit usage")
    if value > 9999999999.99:
        raise BenefitAllocationError("legacy benefit usage exceeds storage bound")
    numerator, denominator = value.as_integer_ratio()
    return (numerator * 100 + denominator - 1) // denominator


def _as_cents_amount(cents: int) -> Decimal:
    if cents > 999_999_999_999:
        raise BenefitAllocationError("benefit usage exceeds storage bound")
    return Decimal((0, tuple(map(int, str(cents))), -2))


def calculate_quota_usage(
    evidence: Iterable[BenefitUsageEvidence], *, period_month: date, period_timezone: str
) -> BenefitQuotaUsage:
    """Sum quota evidence without inferring missing periods or using floats.

    All applications for every duplicate PatientBenefit of the same
    (patient, benefit) pair must be supplied by the caller while holding the
    common quota lock. The caller must also prove complete RLS visibility. The
    helper itself never queries, locks, authorizes or publishes a benefit.
    """
    if (type(period_month) is not date or period_month.day != 1
            or not isinstance(period_timezone, str) or not period_timezone.strip()):
        raise BenefitAllocationError("invalid benefit period")
    monthly = yearly = 0
    try:
        for row in evidence:
            if not isinstance(row, BenefitUsageEvidence) or type(row.legacy) is not bool:
                raise BenefitAllocationError("invalid benefit usage evidence")
            if row.legacy:
                if row.period_month is not None or row.period_timezone is not None:
                    raise BenefitAllocationError("legacy period needs reconciliation")
                cents = _legacy_cents(row.amount)
                monthly += cents
                yearly += cents
                continue
            if (type(row.period_month) is not date or row.period_month.day != 1
                    or not isinstance(row.period_timezone, str) or not row.period_timezone.strip()):
                raise BenefitAllocationError("invalid stored benefit period")
            cents = _money_cents(row.amount)
            # Different timezone provenance cannot prove this event lies
            # outside the current clinic-local month/year near a boundary.
            if row.period_timezone != period_timezone:
                monthly += cents
                yearly += cents
            elif row.period_month.year == period_month.year:
                yearly += cents
                if row.period_month.month == period_month.month:
                    monthly += cents
    except TypeError as exc:
        raise BenefitAllocationError("benefit usage must be iterable") from exc
    return BenefitQuotaUsage(_as_cents_amount(monthly), _as_cents_amount(yearly))
