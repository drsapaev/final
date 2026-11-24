"""Pure age checks do not themselves authorize a benefit."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.services.encounter_benefit_allocation import BenefitAllocationError
from app.services.encounter_benefit_authority import (
    BenefitUsageEvidence,
    age_condition_satisfied,
    calculate_quota_usage,
)


@pytest.mark.parametrize("born", [date(2000, 1, 1), date(2000, 5, 17), None])
def test_unverified_date_never_grants_age_limited_benefit(born):
    assert not age_condition_satisfied(
        born, on=date(2030, 1, 1), age_min=18, age_max=65,
        date_precision_verified=False,
    )


def test_missing_age_rule_does_not_add_a_date_requirement():
    assert age_condition_satisfied(
        None, on=date(2030, 1, 1), age_min=None, age_max=None,
        date_precision_verified=False,
    )


@pytest.mark.parametrize(
    "born,on,minimum,maximum,expected",
    [
        (date(2000, 5, 17), date(2018, 5, 16), 18, None, False),
        (date(2000, 5, 17), date(2018, 5, 17), 18, None, True),
        (date(2000, 5, 17), date(2018, 5, 17), None, 17, False),
        (date(2000, 5, 17), date(2018, 5, 16), None, 17, True),
        (date(2000, 2, 29), date(2018, 2, 28), 18, None, False),
        (date(2000, 2, 29), date(2018, 2, 28), None, 17, False),
        (date(2000, 2, 29), date(2018, 3, 1), 18, None, True),
        (date(2040, 1, 1), date(2030, 1, 1), 0, None, False),
        (date(2000, 1, 1), date(2030, 1, 1), 40, 20, False),
        (date(2000, 1, 1), date(2030, 1, 1), -1, None, False),
        (date(2000, 1, 1), date(2030, 1, 1), True, None, False),
        (datetime(2000, 1, 1), date(2030, 1, 1), 18, None, False),
    ],
)
def test_verified_exact_date_uses_all_supported_age_bounds(born, on, minimum, maximum, expected):
    assert age_condition_satisfied(
        born, on=on, age_min=minimum, age_max=maximum,
        date_precision_verified=True,
    ) is expected


def test_quota_sums_complete_pair_history_and_preserves_period_provenance():
    rows = [
        BenefitUsageEvidence(Decimal("2.00"), False, date(2030, 3, 1), "Asia/Tashkent"),
        BenefitUsageEvidence(Decimal("3.00"), False, date(2030, 2, 1), "Asia/Tashkent"),
        BenefitUsageEvidence(Decimal("4.00"), False, date(2029, 12, 1), "Asia/Tashkent"),
        BenefitUsageEvidence(Decimal("5.00"), False, date(2029, 12, 1), "UTC"),
        # No timestamp can be inferred from the legacy naive time.
        BenefitUsageEvidence(0.30, True),
    ]
    usage = calculate_quota_usage(rows, period_month=date(2030, 3, 1), period_timezone="Asia/Tashkent")
    # 0.30's binary representation is slightly below the cent boundary.
    assert usage.monthly_used == Decimal("7.30")
    assert usage.yearly_used == Decimal("10.30")


def test_legacy_float_is_rounded_toward_more_usage_never_released_quota():
    # 0.07 is represented slightly above 7 cents in binary float.
    usage = calculate_quota_usage(
        [BenefitUsageEvidence(0.07, True)],
        period_month=date(2030, 1, 1), period_timezone="UTC",
    )
    assert usage.monthly_used == usage.yearly_used == Decimal("0.08")


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), -1.0, True, "1.00", Decimal("1.00")])
def test_bad_legacy_amount_never_undercounts_usage(amount):
    with pytest.raises(BenefitAllocationError):
        calculate_quota_usage([BenefitUsageEvidence(amount, True)], period_month=date(2030, 1, 1), period_timezone="UTC")


@pytest.mark.parametrize("row", [
    BenefitUsageEvidence(Decimal("1.00"), True, date(2030, 1, 1), "UTC"),
    BenefitUsageEvidence(Decimal("1.001"), False, date(2030, 1, 1), "UTC"),
    BenefitUsageEvidence(Decimal("NaN"), False, date(2030, 1, 1), "UTC"),
    BenefitUsageEvidence(Decimal("1.00"), False, None, "UTC"),
    BenefitUsageEvidence(Decimal("1.00"), False, date(2030, 1, 2), "UTC"),
    BenefitUsageEvidence(Decimal("1.00"), False, date(2030, 1, 1), ""),
])
def test_invalid_usage_evidence_fails_closed(row):
    with pytest.raises(BenefitAllocationError):
        calculate_quota_usage([row], period_month=date(2030, 1, 1), period_timezone="UTC")


def test_total_overflow_fails_closed():
    rows = [BenefitUsageEvidence(Decimal("9999999999.99"), False, date(2030, 1, 1), "UTC"),
            BenefitUsageEvidence(Decimal("0.01"), False, date(2030, 1, 1), "UTC")]
    with pytest.raises(BenefitAllocationError):
        calculate_quota_usage(rows, period_month=date(2030, 1, 1), period_timezone="UTC")
