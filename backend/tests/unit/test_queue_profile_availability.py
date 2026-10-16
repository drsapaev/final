from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.queue_profile_availability import (
    queue_profile_is_qr_selectable,
    resolve_queue_profile_availability,
)


def _profile(
    *,
    key: str,
    department_key: str | None = None,
    is_active: bool = True,
    show_on_qr_page: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        key=key,
        department_key=department_key,
        is_active=is_active,
        show_on_qr_page=show_on_qr_page,
    )


def _department(key: str, *, active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(key=key, active=active)


def test_profile_without_either_parent_link_is_standalone() -> None:
    profile = _profile(key="unassigned")

    result = resolve_queue_profile_availability(profile, {})

    assert result.state == "available"
    assert result.is_available is True
    assert result.reason_codes == ()
    assert result.parent_department_key is None
    assert result.parent_active is None
    assert queue_profile_is_qr_selectable(profile, result) is True


def test_explicit_and_documented_own_key_parent_resolve() -> None:
    department = _department("cardiology")
    explicitly_linked = _profile(
        key="cardiology-extra", department_key="cardiology"
    )
    own_profile = _profile(key="cardiology", department_key="cardiology")

    explicit_result = resolve_queue_profile_availability(
        explicitly_linked, {"cardiology": department}
    )
    own_result = resolve_queue_profile_availability(
        own_profile, {"cardiology": department}
    )

    assert explicit_result.is_available is True
    assert explicit_result.parent_department_key == "cardiology"
    assert own_result.is_available is True
    assert own_result.parent_department_key == "cardiology"


def test_missing_explicit_parent_fails_closed() -> None:
    profile = _profile(key="specialists", department_key="missing-department")

    result = resolve_queue_profile_availability(profile, {})

    assert result.state == "conflict"
    assert result.is_available is False
    assert result.reason_codes == ("parent_missing",)
    assert queue_profile_is_qr_selectable(profile, result) is False


def test_different_explicit_and_own_key_parents_are_conflicting() -> None:
    profile = _profile(key="department-a", department_key="department-b")
    departments = {
        "department-a": _department("department-a"),
        "department-b": _department("department-b"),
    }

    result = resolve_queue_profile_availability(profile, departments)

    assert result.state == "conflict"
    assert result.is_available is False
    assert result.reason_codes == ("parent_conflict",)
    assert result.parent_department_key is None


def test_department_off_and_manual_archive_have_distinct_reasons() -> None:
    department = _department("parent", active=False)
    linked = _profile(key="child", department_key="parent")
    manually_archived = _profile(
        key="archived-child", department_key="parent", is_active=False
    )

    parent_off = resolve_queue_profile_availability(linked, {"parent": department})
    manual_off = resolve_queue_profile_availability(
        manually_archived, {"parent": department}
    )

    assert parent_off.state == "unavailable"
    assert parent_off.reason_codes == ("parent_inactive",)
    assert manual_off.state == "unavailable"
    assert manual_off.reason_codes == ("manual_archived", "parent_inactive")


@pytest.mark.parametrize(
    ("show_on_qr_page", "expected"),
    [(True, True), (False, False)],
)
def test_qr_selection_keeps_publication_flag_separate_from_availability(
    show_on_qr_page: bool,
    expected: bool,
) -> None:
    profile = _profile(key="standalone", show_on_qr_page=show_on_qr_page)
    availability = resolve_queue_profile_availability(profile, {})

    assert queue_profile_is_qr_selectable(profile, availability) is expected
