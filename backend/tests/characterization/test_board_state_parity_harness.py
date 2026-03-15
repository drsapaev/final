from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.models.clinic import Doctor
from app.models.department import Department
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.queue_profile import QueueProfile
from app.models.setting import Setting
from app.models.user import User
from app.services.board_state_parity_harness import compare_board_state
from app.services.online_queue import get_or_create_day

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
        phone=f"+99891{number:06d}",
        source="online",
        status=status,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _upsert_setting(db_session, *, key: str, value: int) -> None:
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


def test_board_state_parity_harness_keeps_legacy_route_contract_shape_snapshot(
    client, db_session
):
    target_day = date.today()
    date_str = target_day.isoformat()
    _seed_legacy_stats(
        db_session,
        department="Reg",
        date_str=date_str,
        start_number=3,
        is_open=True,
        last_ticket=12,
        waiting=4,
        serving=2,
        done=6,
    )

    response = client.get(
        "/api/v1/board/state",
        params={"department": "Reg", "date": date_str},
    )

    assert response.status_code == 200
    assert response.json() == {
        "department": "Reg",
        "date_str": date_str,
        "is_open": True,
        "start_number": 3,
        "last_ticket": 12,
        "waiting": 4,
        "serving": 2,
        "done": 6,
    }


def test_board_state_parity_harness_proves_queue_and_compatibility_parity_for_mapped_case(
    db_session,
):
    target_day = date.today()
    date_str = target_day.isoformat()
    department = _create_department(
        db_session, key="cardiology", name_ru="Кардиология"
    )
    doctor = _create_doctor(
        db_session,
        username="board_state_harness_doctor",
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
        key="board_state_harness_profile",
        department_key=department.key,
        queue_tags=["cardiology_common"],
    )
    for number, status in [
        (1, "waiting"),
        (2, "called"),
        (3, "served"),
    ]:
        _create_queue_entry(db_session, queue_id=queue.id, number=number, status=status)
    _seed_legacy_stats(
        db_session,
        department=department.key,
        date_str=date_str,
        start_number=5,
        is_open=False,
        last_ticket=3,
        waiting=1,
        serving=1,
        done=1,
    )

    result = compare_board_state(
        db_session,
        department=department.key,
        date_str=date_str,
        display_board=SimpleNamespace(
            name="main_board",
            display_name="Main Board",
            sound_enabled=True,
            colors={
                "primary": "#0066cc",
                "background": "#ffffff",
                "text": "#222222",
            },
        ),
        display_announcements=[
            SimpleNamespace(message="Русское объявление", language="ru", priority=5, active=True),
            SimpleNamespace(message="English notice", language="en", priority=1, active=True),
        ],
    )

    assert result.strict_queue_parity_ok is True
    assert result.compatibility_parity_ok is True
    assert result.strict_queue_matches == {
        "department": True,
        "date_str": True,
        "last_ticket": True,
        "waiting": True,
        "serving": True,
        "done": True,
    }
    assert result.compatibility_matches == {
        "is_open": True,
        "start_number": True,
    }
    assert set(result.noncomparable_display_fields) >= {
        "brand",
        "announcement",
        "announcement_ru",
        "primary_color",
        "bg_color",
        "text_color",
        "sound_default",
    }
    assert result.notes


def test_board_state_parity_harness_documents_legacy_fallback_case_without_forcing_display_parity(
    db_session,
):
    target_day = date.today()
    date_str = target_day.isoformat()
    _seed_legacy_stats(
        db_session,
        department="Reg",
        date_str=date_str,
        start_number=3,
        is_open=True,
        last_ticket=12,
        waiting=4,
        serving=2,
        done=6,
    )

    result = compare_board_state(
        db_session,
        department="Reg",
        date_str=date_str,
        display_board=SimpleNamespace(
            name="fallback_board",
            display_name="Fallback Board",
            sound_enabled=False,
            colors={"primary": "#123456"},
        ),
    )

    assert result.strict_queue_parity_ok is True
    assert result.compatibility_parity_ok is True
    assert result.noncomparable_display_fields == [
        "brand",
        "primary_color",
        "sound_default",
    ]
