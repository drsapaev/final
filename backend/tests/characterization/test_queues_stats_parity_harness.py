from __future__ import annotations

from datetime import date

import pytest

from app.models.clinic import Doctor
from app.models.department import Department
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.queue_profile import QueueProfile
from app.models.setting import Setting
from app.models.user import User
from app.services.online_queue import get_or_create_day
from app.services.queue_stats_parity_harness import compare_queues_stats

pytestmark = pytest.mark.postgres_pilot


def _create_department(db_session, *, key: str, name_ru: str) -> Department:
    department = Department(key=key, name_ru=name_ru, active=True)
    db_session.add(department)
    db_session.commit()
    db_session.refresh(department)
    return department


def _create_doctor(
    db_session,
    *,
    username: str,
    specialty: str,
    department_id: int | None,
) -> Doctor:
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=f"{username} full",
        hashed_password="test-hash",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()

    doctor = Doctor(
        user_id=user.id,
        specialty=specialty,
        department_id=department_id,
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _create_queue_profile(
    db_session,
    *,
    key: str,
    department_key: str,
    queue_tags: list[str],
) -> QueueProfile:
    profile = QueueProfile(
        key=key,
        title=key,
        title_ru=key,
        queue_tags=queue_tags,
        department_key=department_key,
        display_order=1,
        is_active=True,
        show_on_qr_page=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


def _create_daily_queue(
    db_session,
    *,
    specialist_id: int,
    queue_tag: str,
    target_day: date,
) -> DailyQueue:
    queue = DailyQueue(
        day=target_day,
        specialist_id=specialist_id,
        queue_tag=queue_tag,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_queue_entry(
    db_session,
    *,
    queue_id: int,
    number: int,
    status: str,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue_id,
        number=number,
        patient_name=f"Patient {number}",
        phone=f"+99890{number:06d}",
        source="online",
        status=status,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _upsert_setting(
    db_session,
    *,
    key: str,
    value: int,
) -> None:
    setting = (
        db_session.query(Setting)
        .filter(Setting.category == "queue", Setting.key == key)
        .first()
    )
    if setting is None:
        setting = Setting(category="queue", key=key, value=str(value))
        db_session.add(setting)
    else:
        setting.value = str(value)


def _seed_legacy_stats(
    db_session,
    *,
    department: str,
    date_str: str,
    start_number: int = 1,
    is_open: bool = True,
    last_ticket: int = 0,
    waiting: int = 0,
    serving: int = 0,
    done: int = 0,
) -> None:
    get_or_create_day(
        db_session,
        department=department,
        date_str=date_str,
        start_number=start_number,
        open_flag=is_open,
    )
    for name, value in {
        "last_ticket": last_ticket,
        "waiting": waiting,
        "serving": serving,
        "done": done,
    }.items():
        _upsert_setting(
            db_session,
            key=f"{department}::{date_str}::{name}",
            value=value,
        )
    db_session.commit()


@pytest.mark.integration
@pytest.mark.queue
def test_queues_stats_parity_harness_zero_case_matches_strict_fields(
    client,
    db_session,
):
    target_day = date.today()
    date_str = target_day.isoformat()
    department = _create_department(
        db_session, key="cardiology", name_ru="Кардиология"
    )
    doctor = _create_doctor(
        db_session,
        username="w2d_qs_zero_doctor",
        specialty="cardiology_common",
        department_id=department.id,
    )
    queue = _create_daily_queue(
        db_session,
        specialist_id=doctor.id,
        queue_tag="cardiology_common",
        target_day=target_day,
    )
    _create_queue_profile(
        db_session,
        key="w2d_cardiology_profile_zero",
        department_key=department.key,
        queue_tags=["cardiology_common"],
    )
    _seed_legacy_stats(db_session, department=department.key, date_str=date_str)

    response = client.get(
        "/api/v1/queues/stats",
        params={"department": department.key, "d": date_str},
    )
    parity = compare_queues_stats(
        db_session, department=department.key, date_str=date_str
    )

    assert response.status_code == 200
    assert response.json()["last_ticket"] == 0
    assert response.json()["waiting"] == 0
    assert response.json()["serving"] == 0
    assert response.json()["done"] == 0
    assert parity.strict_parity_ok is True
    assert parity.matched_queue_ids == [queue.id]
    assert set(parity.compatibility_mismatches) == {"is_open", "start_number"}


@pytest.mark.integration
@pytest.mark.queue
def test_queues_stats_parity_harness_non_zero_case_matches_strict_fields(
    client,
    db_session,
):
    target_day = date.today()
    date_str = target_day.isoformat()
    department = _create_department(
        db_session, key="cardiology", name_ru="Кардиология"
    )
    doctor = _create_doctor(
        db_session,
        username="w2d_qs_non_zero_doctor",
        specialty="cardiology_common",
        department_id=department.id,
    )
    queue = _create_daily_queue(
        db_session,
        specialist_id=doctor.id,
        queue_tag="cardiology_common",
        target_day=target_day,
    )
    _create_queue_profile(
        db_session,
        key="w2d_cardiology_profile_non_zero",
        department_key=department.key,
        queue_tags=["cardiology_common"],
    )
    for number, status in [
        (1, "waiting"),
        (2, "waiting"),
        (3, "called"),
        (4, "in_service"),
        (5, "diagnostics"),
        (6, "served"),
    ]:
        _create_queue_entry(db_session, queue_id=queue.id, number=number, status=status)
    _seed_legacy_stats(
        db_session,
        department=department.key,
        date_str=date_str,
        last_ticket=6,
        waiting=2,
        serving=3,
        done=1,
    )

    response = client.get(
        "/api/v1/queues/stats",
        params={"department": department.key, "d": date_str},
    )
    parity = compare_queues_stats(
        db_session, department=department.key, date_str=date_str
    )

    assert response.status_code == 200
    assert response.json()["last_ticket"] == parity.legacy.last_ticket == 6
    assert response.json()["waiting"] == parity.legacy.waiting == 2
    assert response.json()["serving"] == parity.legacy.serving == 3
    assert response.json()["done"] == parity.legacy.done == 1
    assert parity.candidate.last_ticket == 6
    assert parity.candidate.waiting == 2
    assert parity.candidate.serving == 3
    assert parity.candidate.done == 1
    assert parity.strict_parity_ok is True
    assert set(parity.compatibility_mismatches) == {"is_open", "start_number"}


@pytest.mark.integration
@pytest.mark.queue
def test_queues_stats_parity_harness_department_mapping_ignores_other_department(
    db_session,
):
    target_day = date.today()
    date_str = target_day.isoformat()

    cardiology = _create_department(
        db_session, key="cardiology", name_ru="Кардиология"
    )
    laboratory = _create_department(
        db_session, key="laboratory", name_ru="Лаборатория"
    )
    cardio_doctor = _create_doctor(
        db_session,
        username="w2d_qs_cardio_map_doctor",
        specialty="cardiology_common",
        department_id=cardiology.id,
    )
    lab_doctor = _create_doctor(
        db_session,
        username="w2d_qs_lab_map_doctor",
        specialty="lab",
        department_id=laboratory.id,
    )
    cardio_queue = _create_daily_queue(
        db_session,
        specialist_id=cardio_doctor.id,
        queue_tag="cardiology_common",
        target_day=target_day,
    )
    lab_queue = _create_daily_queue(
        db_session,
        specialist_id=lab_doctor.id,
        queue_tag="lab",
        target_day=target_day,
    )
    _create_queue_profile(
        db_session,
        key="w2d_cardiology_profile_mapping",
        department_key=cardiology.key,
        queue_tags=["cardiology_common"],
    )
    _create_queue_profile(
        db_session,
        key="w2d_lab_profile_mapping",
        department_key=laboratory.key,
        queue_tags=["lab"],
    )

    _create_queue_entry(db_session, queue_id=cardio_queue.id, number=1, status="waiting")
    _create_queue_entry(db_session, queue_id=cardio_queue.id, number=2, status="served")
    _create_queue_entry(db_session, queue_id=lab_queue.id, number=10, status="waiting")
    _create_queue_entry(db_session, queue_id=lab_queue.id, number=11, status="served")

    _seed_legacy_stats(
        db_session,
        department=cardiology.key,
        date_str=date_str,
        last_ticket=2,
        waiting=1,
        serving=0,
        done=1,
    )

    parity = compare_queues_stats(
        db_session, department=cardiology.key, date_str=date_str
    )

    assert parity.strict_parity_ok is True
    assert parity.matched_queue_ids == [cardio_queue.id]
    assert lab_queue.id not in parity.matched_queue_ids
    assert parity.candidate.last_ticket == 2
    assert parity.candidate.waiting == 1
    assert parity.candidate.serving == 0
    assert parity.candidate.done == 1
