from datetime import date
from types import SimpleNamespace

from app.services.public_booking_calendar_settings import (
    PUBLIC_BOOKING_CALENDAR_CATEGORY,
    PUBLIC_BOOKING_CALENDAR_KEY_PREFIX,
    booking_calendar_from_settings,
    is_public_booking_calendar_setting_key,
)


def _row(year: int, *, confirmed: bool, holidays: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(
        key=f"{PUBLIC_BOOKING_CALENDAR_KEY_PREFIX}{year:04d}",
        category=PUBLIC_BOOKING_CALENDAR_CATEGORY,
        value={
            "year": year,
            "version": 1,
            "is_confirmed": confirmed,
            "holidays": holidays,
            "confirmed_at": "2026-10-24T12:00:00+00:00" if confirmed else None,
            "confirmed_by": 7 if confirmed else None,
        },
    )


def test_calendar_policy_uses_only_confirmed_years_and_explicit_workdays() -> None:
    calendar = booking_calendar_from_settings(
        [
            _row(
                2027,
                confirmed=True,
                holidays=[
                    {"date": "2027-01-01", "is_working_day": False},
                    {"date": "2027-03-08", "is_working_day": True},
                ],
            ),
            _row(
                2028,
                confirmed=False,
                holidays=[{"date": "2028-01-01", "is_working_day": False}],
            ),
        ]
    )

    assert calendar.confirmed_years == frozenset({2027})
    assert calendar.official_holidays == frozenset({date(2027, 1, 1), date(2027, 3, 8)})
    assert calendar.working_exceptions == frozenset({date(2027, 3, 8)})
    assert not calendar.permits_date(date(2028, 1, 1))
    assert not calendar.permits_date(date(2027, 1, 1))
    assert calendar.permits_date(date(2027, 3, 8))


def test_malformed_calendar_fails_closed_without_disabling_other_years() -> None:
    malformed = _row(
        2027,
        confirmed=True,
        holidays=[{"date": "not-a-date", "is_working_day": True}],
    )
    valid = _row(2028, confirmed=True, holidays=[])

    calendar = booking_calendar_from_settings([malformed, valid])

    assert calendar.confirmed_years == frozenset({2028})
    assert not calendar.permits_date(date(2027, 1, 1))
    assert calendar.permits_date(date(2028, 1, 1))


def test_duplicate_stored_holidays_fail_closed() -> None:
    duplicate = _row(
        2027,
        confirmed=True,
        holidays=[
            {"date": "2027-01-01", "is_working_day": False},
            {"date": "2027-01-01", "is_working_day": True},
        ],
    )

    calendar = booking_calendar_from_settings([duplicate])

    assert calendar.confirmed_years == frozenset()
    assert not calendar.permits_date(date(2027, 1, 1))


def test_confirmation_without_audit_metadata_fails_closed() -> None:
    malformed = _row(2027, confirmed=True, holidays=[])
    malformed.value["confirmed_at"] = None
    malformed.value["confirmed_by"] = None

    calendar = booking_calendar_from_settings([malformed])

    assert calendar.confirmed_years == frozenset()
    assert not calendar.permits_date(date(2027, 1, 1))


def test_only_exact_calendar_year_keys_are_reserved() -> None:
    assert is_public_booking_calendar_setting_key("public_booking_calendar_year_2027")
    assert not is_public_booking_calendar_setting_key("public_booking_calendar_year")
    assert not is_public_booking_calendar_setting_key(
        "public_booking_calendar_year_20270"
    )
    assert not is_public_booking_calendar_setting_key(
        "some_public_booking_calendar_year_2027"
    )
