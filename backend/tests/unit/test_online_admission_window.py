from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.crud.daily_queue_creation_policy import (
    LEGACY_POLICY_VERSION,
    ONLINE_ISSUANCES_V1_POLICY_VERSION,
    OnlineAdmissionWindow,
    evaluate_online_admission_window,
    online_admission_window,
    online_window_for_settings,
    parse_hhmm,
)
from app.schemas.clinic import QueueSettingsUpdate


def _fixed_tashkent_time(monkeypatch, module, *, hour: int, minute: int = 0):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            local = datetime(2030, 1, 2, hour, minute)
            return local.replace(tzinfo=tz) if tz is not None else local

    monkeypatch.setattr(module, "datetime", FixedDateTime)
    return FixedDateTime


def _make_v1_queue(db_session, *, day, doctor):
    from app.models.online_queue import DailyQueue

    queue = DailyQueue(
        day=day,
        specialist_id=doctor.id,
        queue_tag=None,
        active=True,
        policy_version=ONLINE_ISSUANCES_V1_POLICY_VERSION,
        online_start_time="07:00",
        online_end_time="09:00",
        max_online_entries=15,
    )
    db_session.add(queue)
    db_session.flush()
    return queue


@pytest.mark.parametrize("value", ["7:00", "24:00", "07:60", "07:0", " 07:00"])
def test_parse_hhmm_rejects_noncanonical_or_out_of_range_values(value):
    with pytest.raises(ValueError, match="HH:MM"):
        parse_hhmm(value, field_name="auto_close_time")


@pytest.mark.parametrize("value", ["7:00", "24:00", "07:60", "07:00:00"])
def test_admin_queue_settings_rejects_noncanonical_cutoff(value):
    with pytest.raises(ValidationError):
        QueueSettingsUpdate(auto_close_time=value)


@pytest.mark.parametrize("start,end", [(7, "07:00"), (7, "06:59"), (23, "00:30")])
def test_admin_queue_settings_rejects_empty_or_overnight_window(start, end):
    with pytest.raises(ValidationError):
        QueueSettingsUpdate(queue_start_hour=start, auto_close_time=end)


def test_admin_queue_settings_openapi_documents_hhmm_pattern():
    schema = QueueSettingsUpdate.model_json_schema()

    assert schema["properties"]["auto_close_time"]["pattern"] == (
        r"^(?:[01]\d|2[0-3]):[0-5]\d$"
    )


def test_legacy_policy_keeps_start_gate_without_admission_cutoff():
    start_time, end_time = online_window_for_settings(
        {"queue_start_hour": 8, "auto_close_time": "10:00"},
        policy_version=LEGACY_POLICY_VERSION,
    )

    assert start_time.strftime("%H:%M") == "08:00"
    assert end_time is None


def test_v1_row_uses_frozen_window_instead_of_changed_settings():
    row = SimpleNamespace(
        policy_version=ONLINE_ISSUANCES_V1_POLICY_VERSION,
        online_start_time="08:00",
        online_end_time="10:00",
    )

    window = online_admission_window(
        daily_queue=row,
        settings={"queue_start_hour": 6, "auto_close_time": "07:00"},
    )

    assert window.start_time.strftime("%H:%M") == "08:00"
    assert window.end_time.strftime("%H:%M") == "10:00"


def test_rowless_v1_window_uses_fresh_settings_and_creation_policy(
    monkeypatch,
):
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")

    window = online_admission_window(
        daily_queue=None,
        settings={"queue_start_hour": 8, "auto_close_time": "10:30"},
    )

    assert window.policy_version == ONLINE_ISSUANCES_V1_POLICY_VERSION
    assert window.start_time.strftime("%H:%M") == "08:00"
    assert window.end_time.strftime("%H:%M") == "10:30"


@pytest.mark.parametrize(
    ("clock", "expected"),
    [
        ("07:59", "before_start"),
        ("08:00", "available"),
        ("09:59", "available"),
        ("10:00", "after_end"),
        ("10:01", "after_end"),
    ],
)
def test_v1_window_uses_half_open_boundaries(clock, expected):
    start_time, end_time = online_window_for_settings(
        {"queue_start_hour": 8, "auto_close_time": "10:00"},
        policy_version=ONLINE_ISSUANCES_V1_POLICY_VERSION,
    )
    now = datetime.combine(date(2026, 10, 1), datetime.strptime(clock, "%H:%M").time())
    window = OnlineAdmissionWindow(
        ONLINE_ISSUANCES_V1_POLICY_VERSION,
        start_time,
        end_time,
    )

    assert evaluate_online_admission_window(date(2026, 10, 1), now, window) == expected


def test_window_applies_same_day_clock_in_the_supplied_clinic_timezone():
    clinic_now = datetime(2026, 10, 1, 19, 30, tzinfo=ZoneInfo("UTC")).astimezone(
        ZoneInfo("Asia/Tashkent")
    )
    start_time, end_time = online_window_for_settings(
        {"queue_start_hour": 7, "auto_close_time": "09:00"},
        policy_version=ONLINE_ISSUANCES_V1_POLICY_VERSION,
    )
    window = OnlineAdmissionWindow(
        ONLINE_ISSUANCES_V1_POLICY_VERSION,
        start_time,
        end_time,
    )

    assert clinic_now.date() == date(2026, 10, 2)
    assert (
        evaluate_online_admission_window(clinic_now.date(), clinic_now, window)
        == "before_start"
    )


def test_future_date_preserves_same_day_window_bypass():
    start_time, end_time = online_window_for_settings(
        {"queue_start_hour": 8, "auto_close_time": "10:00"},
        policy_version=ONLINE_ISSUANCES_V1_POLICY_VERSION,
    )
    window = OnlineAdmissionWindow(
        ONLINE_ISSUANCES_V1_POLICY_VERSION,
        start_time,
        end_time,
    )

    assert (
        evaluate_online_admission_window(
            date(2026, 10, 2),
            datetime(2026, 10, 1, 23, 0),
            window,
        )
        == "available"
    )


@pytest.mark.unit
def test_public_status_reports_same_v1_cutoff_as_availability(db_session, monkeypatch):
    import app.api.v1.endpoints.online_queue_new as online_queue_endpoint
    import app.crud.clinic as clinic_crud
    import app.crud.online_queue as online_queue_crud
    from app.models.clinic import Doctor

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)
    monkeypatch.setattr(online_queue_crud, "get_queue_settings", lambda db: settings)
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
    _fixed_tashkent_time(monkeypatch, online_queue_crud, hour=9)
    _fixed_tashkent_time(monkeypatch, online_queue_endpoint, hour=9)

    doctor = Doctor(specialty="cardiology")
    db_session.add(doctor)
    db_session.flush()
    queue = _make_v1_queue(db_session, day=date(2030, 1, 2), doctor=doctor)

    availability = online_queue_crud.check_queue_availability(
        db_session, queue.day, doctor.id
    )
    public_status = online_queue_endpoint.check_queue_status(
        day=queue.day, specialist_id=doctor.id, db=db_session
    )

    assert availability["available"] is False
    assert availability["reason"] == "AFTER_CUTOFF"
    assert availability["end_time"] == "09:00"
    assert public_status.within_hours is False
    assert public_status.policy_version == ONLINE_ISSUANCES_V1_POLICY_VERSION
    assert public_status.queue_end_time == "09:00"

    rowless_doctor = Doctor(specialty="dermatology")
    db_session.add(rowless_doctor)
    db_session.flush()
    rowless = online_queue_crud.check_queue_availability(
        db_session, queue.day, rowless_doctor.id
    )
    rowless_status = online_queue_endpoint.check_queue_status(
        day=queue.day, specialist_id=rowless_doctor.id, db=db_session
    )
    assert rowless["available"] is False
    assert rowless["reason"] == "AFTER_CUTOFF"
    assert rowless["policy_version"] == ONLINE_ISSUANCES_V1_POLICY_VERSION
    assert rowless["end_time"] == "09:00"
    assert rowless_status.within_hours is False
    assert rowless_status.policy_version == ONLINE_ISSUANCES_V1_POLICY_VERSION
    assert rowless["queue_length"] == 0
    assert rowless["max_online_entries"] == rowless_doctor.max_online_per_day
    assert rowless["online_issued_count"] == 0
    assert rowless["online_bookings_remaining"] == rowless_doctor.max_online_per_day


@pytest.mark.unit
def test_v1_availability_uses_issued_counter_instead_of_live_queue_length(
    db_session, monkeypatch
):
    import app.crud.clinic as clinic_crud
    import app.crud.online_queue as online_queue_crud
    from app.models.clinic import Doctor

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)
    monkeypatch.setattr(online_queue_crud, "get_queue_settings", lambda db: settings)
    _fixed_tashkent_time(monkeypatch, online_queue_crud, hour=8)

    doctor = Doctor(specialty="cardiology")
    db_session.add(doctor)
    db_session.flush()
    queue = _make_v1_queue(db_session, day=date(2030, 1, 2), doctor=doctor)
    queue.max_online_entries = 2
    queue.online_issued_count = 2
    db_session.flush()

    result = online_queue_crud.check_queue_availability(
        db_session, queue.day, doctor.id
    )

    assert result["available"] is False
    assert result["reason"] == "QUEUE_FULL"
    assert result["queue_length"] == 0
    assert result["policy_version"] == ONLINE_ISSUANCES_V1_POLICY_VERSION
    assert result["max_online_entries"] == 2
    assert result["online_issued_count"] == 2
    assert result["online_bookings_remaining"] == 0


@pytest.mark.unit
def test_legacy_availability_ignores_completed_entries_for_active_limit(
    db_session, monkeypatch
):
    import app.crud.clinic as clinic_crud
    import app.crud.online_queue as online_queue_crud
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)
    monkeypatch.setattr(online_queue_crud, "get_queue_settings", lambda db: settings)
    _fixed_tashkent_time(monkeypatch, online_queue_crud, hour=8)

    doctor = Doctor(specialty="cardiology")
    db_session.add(doctor)
    db_session.flush()
    queue = DailyQueue(
        day=date(2030, 1, 2),
        specialist_id=doctor.id,
        queue_tag=None,
        active=True,
        policy_version=LEGACY_POLICY_VERSION,
        online_start_time="07:00",
        online_end_time="09:00",
        max_online_entries=1,
    )
    db_session.add(queue)
    db_session.flush()
    db_session.add(
        OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_name="Synthetic Patient",
            source="online",
            status="served",
        )
    )
    db_session.flush()

    result = online_queue_crud.check_queue_availability(
        db_session, queue.day, doctor.id
    )

    assert result["available"] is True
    assert result["queue_length"] == 0
    assert result["policy_version"] == LEGACY_POLICY_VERSION
    assert result["online_issued_count"] is None
    assert result["online_bookings_remaining"] is None


@pytest.mark.unit
def test_concrete_qr_reports_v1_quota_from_persisted_issuances(db_session, monkeypatch):
    import app.crud.clinic as clinic_crud
    import app.services.qr_queue_service as qr_queue_service_module
    import app.services.queue_service as queue_service_module
    from app.api.v1.endpoints.qr_queue._helpers import QRTokenInfoResponse
    from app.models.clinic import Doctor
    from app.models.online_queue import QueueToken
    from app.services.qr_queue import QRQueueService

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)
    monkeypatch.delenv("DISABLE_QUEUE_TIME_RESTRICTIONS", raising=False)
    _fixed_tashkent_time(monkeypatch, queue_service_module, hour=8)
    _fixed_tashkent_time(monkeypatch, qr_queue_service_module, hour=8)

    doctor = Doctor(specialty="cardiology")
    db_session.add(doctor)
    db_session.flush()
    queue = _make_v1_queue(db_session, day=date(2030, 1, 2), doctor=doctor)
    queue.max_online_entries = 3
    queue.online_issued_count = 2
    token = QueueToken(
        token="synthetic-v1-quota-report",
        day=queue.day,
        specialist_id=doctor.id,
        expires_at=datetime(2030, 1, 3, 0, 0),
        active=True,
    )
    db_session.add(token)
    db_session.flush()

    service = QRQueueService(db_session)
    result = service._check_online_time_restrictions(token.token)
    token_info = service.get_qr_token_info(token.token)
    response = QRTokenInfoResponse(**token_info)

    assert result["allowed"] is True, result
    assert result["current_entries"] == 0
    assert result["max_online_entries"] == 3
    assert result["online_issued_count"] == 2
    assert result["online_bookings_remaining"] == 1
    assert response.max_online_entries == 3
    assert response.online_issued_count == 2
    assert response.online_bookings_remaining == 1


@pytest.mark.unit
def test_concrete_qr_compatibility_counts_only_online_entries(db_session, monkeypatch):
    import app.crud.clinic as clinic_crud
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
    from app.services.qr_queue import QRQueueService

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)

    doctor = Doctor(specialty="cardiology")
    db_session.add(doctor)
    db_session.flush()
    queue = DailyQueue(
        day=date(2030, 1, 2),
        specialist_id=doctor.id,
        queue_tag=None,
        active=True,
        policy_version=LEGACY_POLICY_VERSION,
        online_start_time="07:00",
        online_end_time="09:00",
        max_online_entries=4,
    )
    db_session.add(queue)
    db_session.flush()
    db_session.add_all(
        [
            OnlineQueueEntry(
                queue_id=queue.id,
                number=1,
                source="online",
                status="waiting",
            ),
            OnlineQueueEntry(
                queue_id=queue.id,
                number=2,
                source="registrar",
                status="waiting",
            ),
            OnlineQueueEntry(
                queue_id=queue.id,
                number=3,
                source="online",
                status="served",
            ),
        ]
    )
    token = QueueToken(
        token="synthetic-legacy-compat-counts",
        day=queue.day,
        specialist_id=doctor.id,
        expires_at=datetime(2030, 1, 3),
        active=True,
    )
    db_session.add(token)
    db_session.flush()

    result = QRQueueService(db_session).get_qr_token_info(token.token)

    assert result["queue_length"] == 2
    assert result["current_entries"] == 1
    assert result["remaining_slots"] == 3
    assert result["online_issued_count"] is None
    assert result["online_bookings_remaining"] is None


@pytest.mark.unit
def test_opened_concrete_qr_reports_persisted_policy_version(db_session, monkeypatch):
    import app.crud.clinic as clinic_crud
    from app.models.clinic import Doctor
    from app.models.online_queue import QueueToken
    from app.services.qr_queue import QRQueueService

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)

    doctor = Doctor(specialty="cardiology")
    db_session.add(doctor)
    db_session.flush()
    queue = _make_v1_queue(db_session, day=date(2030, 1, 2), doctor=doctor)
    queue.opened_at = datetime(2030, 1, 2, 8, 0)
    token = QueueToken(
        token="synthetic-opened-v1-policy",
        day=queue.day,
        specialist_id=doctor.id,
        expires_at=datetime(2030, 1, 3),
        active=True,
    )
    db_session.add(token)
    db_session.flush()

    result = QRQueueService(db_session).get_qr_token_info(token.token)

    assert result["status"] == "closed_reception_opened"
    assert result["policy_version"] == ONLINE_ISSUANCES_V1_POLICY_VERSION


@pytest.mark.unit
def test_rowless_qr_does_not_synthesize_quota_for_inactive_resource_identity(
    db_session, monkeypatch
):
    import app.crud.clinic as clinic_crud
    from app.api.v1.endpoints.qr_queue._helpers import QRTokenInfoResponse
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, QueueResource, QueueToken
    from app.services.qr_queue import QRQueueService

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")

    doctor = Doctor(specialty="synthetic-resource-tag")
    resource = QueueResource(
        code="synthetic-resource-tag",
        queue_tag="synthetic-resource-tag",
        display_name="Synthetic resource",
        active=True,
        max_online_per_day=5,
    )
    db_session.add_all([doctor, resource])
    db_session.flush()
    queue = DailyQueue(
        day=date(2030, 1, 2),
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag=resource.queue_tag,
        active=False,
        policy_version=ONLINE_ISSUANCES_V1_POLICY_VERSION,
        online_start_time="07:00",
        online_end_time="09:00",
        max_online_entries=5,
        online_issued_count=3,
    )
    token = QueueToken(
        token="synthetic-inactive-resource-quota",
        day=queue.day,
        specialist_id=doctor.id,
        expires_at=datetime(2030, 1, 3),
        active=True,
    )
    db_session.add_all([queue, token])
    db_session.flush()

    result = QRQueueService(db_session).get_qr_token_info(token.token)
    response = QRTokenInfoResponse(**result)

    assert result["status"] == "queue_inactive"
    assert result["policy_version"] is None
    assert result["max_online_entries"] is None
    assert result["online_issued_count"] is None
    assert result["online_bookings_remaining"] is None
    assert response.policy_version is None
    assert response.online_issued_count is None
    assert response.online_bookings_remaining is None


@pytest.mark.unit
def test_concrete_qr_keeps_future_date_advisory_available_at_quota(
    db_session, monkeypatch
):
    import app.crud.clinic as clinic_crud
    import app.services.qr_queue_service as qr_queue_service_module
    import app.services.queue_service as queue_service_module
    from app.models.clinic import Doctor
    from app.models.online_queue import QueueToken
    from app.services.qr_queue import QRQueueService

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)
    monkeypatch.delenv("DISABLE_QUEUE_TIME_RESTRICTIONS", raising=False)
    _fixed_tashkent_time(monkeypatch, queue_service_module, hour=8)
    _fixed_tashkent_time(monkeypatch, qr_queue_service_module, hour=8)

    doctor = Doctor(specialty="cardiology")
    db_session.add(doctor)
    db_session.flush()
    future_day = date(2030, 1, 3)
    queue = _make_v1_queue(db_session, day=future_day, doctor=doctor)
    queue.max_online_entries = 1
    queue.online_issued_count = 1
    token = QueueToken(
        token="synthetic-v1-future-quota-report",
        day=future_day,
        specialist_id=doctor.id,
        expires_at=datetime(2030, 1, 4, 0, 0),
        active=True,
    )
    db_session.add(token)
    db_session.flush()

    result = QRQueueService(db_session)._check_online_time_restrictions(token.token)

    # Future-date availability remains advisory as in the existing contract;
    # the report still exposes that the persisted quota has no room left.
    assert result["allowed"] is True, result
    assert result["status"] == "available"
    assert result["online_issued_count"] == 1
    assert result["online_bookings_remaining"] == 0


@pytest.mark.unit
def test_rowless_concrete_qr_token_info_preserves_owner_default_quota(
    db_session, monkeypatch
):
    import app.crud.clinic as clinic_crud
    import app.services.qr_queue_service as qr_queue_service_module
    import app.services.queue_service as queue_service_module
    from app.api.v1.endpoints.qr_queue._helpers import QRTokenInfoResponse
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, QueueToken
    from app.services.qr_queue import QRQueueService

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
    monkeypatch.delenv("DISABLE_QUEUE_TIME_RESTRICTIONS", raising=False)
    _fixed_tashkent_time(monkeypatch, queue_service_module, hour=8)
    _fixed_tashkent_time(monkeypatch, qr_queue_service_module, hour=8)

    doctor = Doctor(specialty="cardiology", max_online_per_day=4)
    db_session.add(doctor)
    db_session.flush()
    token = QueueToken(
        token="synthetic-rowless-quota-report",
        day=date(2030, 1, 2),
        specialist_id=doctor.id,
        expires_at=datetime(2030, 1, 3, 0, 0),
        active=True,
    )
    db_session.add(token)
    db_session.flush()

    service = QRQueueService(db_session)
    info = service.get_qr_token_info(token.token)
    response = QRTokenInfoResponse(**info)

    assert (
        db_session.query(DailyQueue)
        .filter(DailyQueue.specialist_id == doctor.id, DailyQueue.day == token.day)
        .first()
        is None
    )
    assert response.max_online_entries == 4
    assert response.online_issued_count == 0
    assert response.online_bookings_remaining == 4


@pytest.mark.unit
def test_specific_qr_precheck_rejects_v1_at_exact_cutoff(db_session, monkeypatch):
    import app.crud.clinic as clinic_crud
    import app.services.qr_queue_service as qr_queue_service_module
    import app.services.queue_service as queue_service_module
    from app.models.clinic import Doctor
    from app.models.online_queue import QueueToken
    from app.services.qr_queue import QRQueueService

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)
    monkeypatch.delenv("DISABLE_QUEUE_TIME_RESTRICTIONS", raising=False)
    _fixed_tashkent_time(monkeypatch, queue_service_module, hour=9)
    _fixed_tashkent_time(monkeypatch, qr_queue_service_module, hour=9)

    doctor = Doctor(specialty="cardiology")
    db_session.add(doctor)
    db_session.flush()
    queue = _make_v1_queue(db_session, day=date(2030, 1, 2), doctor=doctor)
    token = QueueToken(
        token="synthetic-v1-cutoff",
        day=queue.day,
        specialist_id=doctor.id,
        expires_at=datetime(2030, 1, 3, 0, 0),
        active=True,
    )
    db_session.add(token)
    db_session.flush()

    result = QRQueueService(db_session)._check_online_time_restrictions(token.token)

    assert result["allowed"] is False, result
    assert result["status"] == "after_end_time"
    assert result["policy_version"] == ONLINE_ISSUANCES_V1_POLICY_VERSION
    assert result["end_time"] == "09:00"
    assert result["max_online_entries"] == 15
    assert result["online_issued_count"] == 0
    assert result["online_bookings_remaining"] == 15


@pytest.mark.unit
def test_clinic_wide_legacy_qr_before_start_returns_countdown_metadata(
    db_session, monkeypatch
):
    import app.crud.clinic as clinic_crud
    import app.services.qr_queue._queue_ops as qr_queue_ops_module
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, QueueToken
    from app.services.qr_queue import QRQueueService

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)
    monkeypatch.setattr(
        qr_queue_ops_module,
        "_now",
        lambda tz: datetime(2030, 1, 2, 6, 30, tzinfo=tz),
    )
    monkeypatch.delenv("DISABLE_QUEUE_TIME_RESTRICTIONS", raising=False)

    day = date(2030, 1, 2)
    doctor = Doctor(specialty="cardiology")
    db_session.add(doctor)
    db_session.flush()
    queue = DailyQueue(
        day=day,
        specialist_id=doctor.id,
        queue_tag=None,
        active=True,
        policy_version=LEGACY_POLICY_VERSION,
        online_start_time="07:00",
        online_end_time="09:00",
        max_online_entries=15,
    )
    db_session.add(queue)
    db_session.add(
        QueueToken(
            token="synthetic-clinicwide-legacy-before-start",
            day=day,
            specialist_id=None,
            is_clinic_wide=True,
            expires_at=datetime(2030, 1, 3),
            active=True,
        )
    )
    db_session.flush()

    result = QRQueueService(db_session)._check_online_time_restrictions(
        "synthetic-clinicwide-legacy-before-start"
    )

    assert result["allowed"] is False, result
    assert result["status"] == "before_start_time"
    assert result["policy_version"] == LEGACY_POLICY_VERSION
    assert result["minutes_until_open"] == 30
    assert result["opens_at_datetime"] == "2030-01-02T07:00:00+05:00"
    assert result["countdown_text"] == "Откроется через 30 мин"


@pytest.mark.unit
def test_clinic_wide_qr_uses_any_available_queue_in_mixed_legacy_day(
    db_session, monkeypatch
):
    import app.crud.clinic as clinic_crud
    import app.services.qr_queue_service as qr_queue_service_module
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
    from app.services.qr_queue import QRQueueService

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)
    _fixed_tashkent_time(monkeypatch, qr_queue_service_module, hour=9)

    day = date(2030, 1, 2)
    v1_doctor = Doctor(specialty="cardiology")
    legacy_doctor = Doctor(specialty="dermatology")
    db_session.add_all([v1_doctor, legacy_doctor])
    db_session.flush()
    v1_queue = _make_v1_queue(db_session, day=day, doctor=v1_doctor)
    db_session.add(
        DailyQueue(
            day=day,
            specialist_id=legacy_doctor.id,
            queue_tag=None,
            active=True,
            policy_version=LEGACY_POLICY_VERSION,
            online_start_time="07:00",
            online_end_time="09:00",
            max_online_entries=15,
        )
    )
    db_session.add_all(
        [
            OnlineQueueEntry(
                queue_id=v1_queue.id,
                number=1,
                status="waiting",
                source="online",
            ),
            OnlineQueueEntry(
                queue_id=v1_queue.id,
                number=2,
                status="called",
                source="registrar",
            ),
        ]
    )
    token = QueueToken(
        token="synthetic-clinicwide-mixed-policy",
        day=day,
        specialist_id=None,
        is_clinic_wide=True,
        expires_at=datetime(2030, 1, 3),
        active=True,
    )
    db_session.add(token)
    db_session.flush()

    result = QRQueueService(db_session)._check_online_time_restrictions(token.token)

    assert result["allowed"] is True, result
    assert result["status"] == "available"
    assert result["policy_version"] == LEGACY_POLICY_VERSION
    assert result["end_time"] is None
    assert result.get("max_online_entries") is None
    assert result.get("online_issued_count") is None
    assert result.get("online_bookings_remaining") is None
    assert result["current_entries"] == 1
    assert result["queue_length"] == 2


@pytest.mark.unit
def test_clinic_wide_qr_keeps_later_direction_available_after_another_opens(
    db_session, monkeypatch
):
    import app.crud.clinic as clinic_crud
    import app.services.qr_queue_service as qr_queue_service_module
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, QueueToken
    from app.services.qr_queue import QRQueueService

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "10:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)
    _fixed_tashkent_time(monkeypatch, qr_queue_service_module, hour=9)
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")

    day = date(2030, 1, 2)
    v1_doctor = Doctor(specialty="cardiology")
    legacy_doctor = Doctor(specialty="dermatology")
    db_session.add_all([v1_doctor, legacy_doctor])
    db_session.flush()
    v1_queue = _make_v1_queue(db_session, day=day, doctor=v1_doctor)
    v1_queue.online_end_time = "10:00"
    db_session.add(
        DailyQueue(
            day=day,
            specialist_id=legacy_doctor.id,
            queue_tag=None,
            active=True,
            policy_version=LEGACY_POLICY_VERSION,
            online_start_time="07:00",
            online_end_time="09:00",
            opened_at=datetime(2030, 1, 2, 9, 0),
            max_online_entries=15,
        )
    )
    token = QueueToken(
        token="synthetic-clinicwide-opened-legacy-v1-available",
        day=day,
        specialist_id=None,
        is_clinic_wide=True,
        expires_at=datetime(2030, 1, 3),
        active=True,
    )
    db_session.add(token)
    db_session.flush()

    result = QRQueueService(db_session)._check_online_time_restrictions(token.token)

    assert result["allowed"] is True, result
    assert result["status"] == "available"
    assert result["policy_version"] == ONLINE_ISSUANCES_V1_POLICY_VERSION
    assert result["end_time"] == "10:00"


@pytest.mark.unit
def test_clinic_wide_qr_reports_length_when_all_queues_are_opened(
    db_session, monkeypatch
):
    import app.crud.clinic as clinic_crud
    from app.models.clinic import Doctor
    from app.models.online_queue import OnlineQueueEntry, QueueToken
    from app.services.qr_queue import QRQueueService

    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: settings)

    day = date(2030, 1, 2)
    doctors = [Doctor(specialty="cardiology"), Doctor(specialty="dermatology")]
    db_session.add_all(doctors)
    db_session.flush()
    queues = [_make_v1_queue(db_session, day=day, doctor=doctor) for doctor in doctors]
    for queue in queues:
        queue.opened_at = datetime(2030, 1, 2, 8, 0)
    db_session.add_all(
        [
            OnlineQueueEntry(
                queue_id=queues[0].id,
                number=1,
                source="online",
                status="waiting",
            ),
            OnlineQueueEntry(
                queue_id=queues[1].id,
                number=1,
                source="registrar",
                status="called",
            ),
            OnlineQueueEntry(
                queue_id=queues[1].id,
                number=2,
                source="online",
                status="served",
            ),
        ]
    )
    token = QueueToken(
        token="synthetic-clinic-wide-opened-length",
        day=day,
        specialist_id=None,
        is_clinic_wide=True,
        expires_at=datetime(2030, 1, 3),
        active=True,
    )
    db_session.add(token)
    db_session.flush()

    result = QRQueueService(db_session).get_qr_token_info(token.token)

    assert result["status"] == "closed_reception_opened"
    assert result["queue_length"] == 2
    assert result["max_online_entries"] is None
    assert result["online_issued_count"] is None
    assert result["online_bookings_remaining"] is None
