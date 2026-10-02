"""PR #3511 review P1 (round 5): the explicit ``Service.doctor_id`` pin.

The catalog flags (``requires_doctor``/``is_consultation``) and the
explicit assignment (``Service.doctor_id``) are saved INDEPENDENTLY by
the admin catalog. The historical early exits keyed on the raw flags
bypassed the pin entirely:

- ``assert_doctor_eligible_for_service`` returned before the
  exact-doctor check, so a pinned unflagged service booked to ANY
  doctor (or none) without the 409;
- ``doctor_selection_required_for_surface`` answered False, so the
  wizard never offered the pinned doctor's card;
- ``doctor_booking_unavailable_reason`` answered None, hiding the
  resource-ownership conflict of a pin on a resource-routed tag.

These pins use duck-typed namespace services (the surfaces share the
same duck-typing contract — ``getattr``), tag-less for the guard: an
empty queue_tag short-circuits the resource router BEFORE any DB read,
so no session is needed and an accidental query would explode loudly.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.registrar_doctor_eligibility import (
    assert_doctor_eligible_for_service,
    doctor_booking_unavailable_reason,
    doctor_selection_required_for_surface,
    service_has_explicit_doctor_assignment,
)


class _NoDb:
    """Fail loudly on any accidental ORM use."""

    def __getattr__(self, name: str):  # pragma: no cover - guard rail
        raise AssertionError(
            f"unexpected DB access via _NoDb.{name}: the pinned-contract "
            "checks must be decidable without a session"
        )


def _svc(
    *,
    requires_doctor: bool = False,
    is_consultation: bool = False,
    doctor_id: int | None = None,
    queue_tag: str | None = None,
    name: str = "Закреплённая услуга",
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        requires_doctor=requires_doctor,
        is_consultation=is_consultation,
        doctor_id=doctor_id,
        queue_tag=queue_tag,
        department_key=None,
    )


# ── service_has_explicit_doctor_assignment ─────────────────────────────────


@pytest.mark.unit
def test_explicit_assignment_detects_pin_and_duck_types():
    assert service_has_explicit_doctor_assignment(_svc(doctor_id=7)) is True
    assert service_has_explicit_doctor_assignment(_svc(doctor_id=None)) is False
    # поверхности без ORM-атрибута: отсутствие поля = «назначения нет»
    assert (
        service_has_explicit_doctor_assignment(
            SimpleNamespace(requires_doctor=True, is_consultation=False)
        )
        is False
    )


# ── doctor_selection_required_for_surface ──────────────────────────────────


@pytest.mark.unit
def test_unflagged_pinned_doctor_queue_tag_requires_selection():
    """P1: пин без флагов на врачебном теге → выбор врача обязателен.

    До фикса ранний выход по сырым флагам возвращал False — мастер не
    показывал карточку назначенного врача вообще.
    """
    decision = doctor_selection_required_for_surface(
        _NoDb(),
        _svc(doctor_id=7, queue_tag="cardio"),
        None,
        resource_routed_tags=set(),
    )
    assert decision is True


@pytest.mark.unit
def test_unflagged_pinned_resource_tag_stays_resource_surface():
    """Пин на ресурсном теге: владелец очереди важнее — поверхность
    ресурсная, закрепление декоративно (конфиг-ошибка для админа)."""
    decision = doctor_selection_required_for_surface(
        _NoDb(),
        _svc(doctor_id=7, queue_tag="ecg"),
        None,
        resource_routed_tags={"ecg"},
    )
    assert decision is False


@pytest.mark.unit
def test_unflagged_unpinned_service_keeps_legacy_decision():
    assert (
        doctor_selection_required_for_surface(
            _NoDb(), _svc(queue_tag="cardio"), None, resource_routed_tags=set()
        )
        is False
    )
    assert (
        doctor_selection_required_for_surface(
            _NoDb(),
            _svc(requires_doctor=True, queue_tag="ecg"),
            None,
            resource_routed_tags={"ecg"},
        )
        is False
    )
    assert (
        doctor_selection_required_for_surface(
            _NoDb(),
            _svc(is_consultation=True, queue_tag="ecg"),
            None,
            resource_routed_tags={"ecg"},
        )
        is True
    )


# ── doctor_booking_unavailable_reason ──────────────────────────────────────


@pytest.mark.unit
def test_booking_unavailable_reason_for_unflagged_pin():
    """Врачебный тег → врач-запись доступна (со своим врачом); ресурсный
    тег → причина resource_queue — тот же контракт, что у flagged K10."""
    assert (
        doctor_booking_unavailable_reason(_svc(doctor_id=7, queue_tag="cardio"), set())
        is None
    )
    assert (
        doctor_booking_unavailable_reason(_svc(doctor_id=7, queue_tag="ecg"), {"ecg"})
        == "resource_queue"
    )
    assert doctor_booking_unavailable_reason(_svc(queue_tag="ecg"), {"ecg"}) is None


# ── assert_doctor_eligible_for_service ─────────────────────────────────────


@pytest.mark.unit
def test_guard_rejects_other_doctor_for_unflagged_pin_without_db():
    """P1 (ядро): ранний return по флагам больше не обходить пин —
    несовпадение врача ловится ДО каких-либо обращений к БД."""
    with pytest.raises(HTTPException) as exc:
        assert_doctor_eligible_for_service(
            _NoDb(), _svc(doctor_id=7, queue_tag=None), 8
        )
    assert exc.value.status_code == 409
    assert "назначена другому врачу" in exc.value.detail


@pytest.mark.unit
def test_guard_requires_a_doctor_for_unflagged_pin():
    with pytest.raises(HTTPException) as exc:
        assert_doctor_eligible_for_service(
            _NoDb(), _svc(doctor_id=7, queue_tag=None), None
        )
    assert exc.value.status_code == 400
    assert "требует выбора врача" in exc.value.detail


@pytest.mark.unit
def test_guard_keeps_silent_for_unflagged_unpinned_service():
    """Контроль обратной совместимости: обычная безфлажковая услуга без
    назначения по-прежнему проходит гвард без вопросов (лаб-семантика)."""
    assert (
        assert_doctor_eligible_for_service(
            _NoDb(), _svc(queue_tag=None, doctor_id=None), None
        )
        is None
    )
