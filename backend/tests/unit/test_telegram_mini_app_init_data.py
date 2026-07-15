from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest

from app.services.telegram_mini_app_init_data import (
    TelegramMiniAppInitDataError,
    TelegramMiniAppSessionScopeError,
    build_telegram_mini_app_appointment_booking_draft,
    build_telegram_mini_app_appointment_booking_preview,
    require_telegram_mini_app_patient_scope,
    require_telegram_mini_app_staff_scope,
    resolve_telegram_mini_app_session_scope,
    validate_telegram_mini_app_init_data,
)
from app.models.telegram_config import TelegramUser
from app.models.user import User


BOT_TOKEN = "123456:test-mini-app-token"


def _signed_init_data(params: dict[str, str], bot_token: str = BOT_TOKEN) -> str:
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    payload_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode({**params, "hash": payload_hash})


def _validated_init_data(telegram_id: int, *, now: datetime):
    init_data = _signed_init_data(
        {
            "auth_date": str(int(now.timestamp())),
            "query_id": "AAEAAAE",
            "user": json.dumps({"id": telegram_id}, separators=(",", ":")),
        }
    )
    return validate_telegram_mini_app_init_data(
        init_data,
        bot_token=BOT_TOKEN,
        now=now,
        replay_check=False,  # M4-P0-2: disable replay protection in unit tests
    )


def _telegram_user(chat_id: int, **overrides) -> TelegramUser:
    defaults = {
        "chat_id": chat_id,
        "language_code": "ru",
        "active": True,
        "blocked": False,
        "notifications_enabled": False,
        "appointment_reminders": False,
        "lab_notifications": False,
    }
    defaults.update(overrides)
    return TelegramUser(**defaults)


def test_validate_telegram_mini_app_init_data_accepts_signed_payload():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    init_data = _signed_init_data(
        {
            "auth_date": str(int((now - timedelta(minutes=3)).timestamp())),
            "query_id": "AAEAAAE",
            "user": json.dumps(
                {"id": 42, "first_name": "Ali", "language_code": "ru"},
                separators=(",", ":"),
            ),
        }
    )

    result = validate_telegram_mini_app_init_data(
        init_data,
        bot_token=BOT_TOKEN,
        now=now,
    )

    assert result.user == {"id": 42, "first_name": "Ali", "language_code": "ru"}
    assert result.fields["query_id"] == "AAEAAAE"
    assert "hash" not in result.fields
    assert result.age_seconds == 180


def test_validate_telegram_mini_app_init_data_rejects_forged_hash():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    init_data = _signed_init_data(
        {
            "auth_date": str(int(now.timestamp())),
            "query_id": "AAEAAAE",
            "user": json.dumps({"id": 42}, separators=(",", ":")),
        }
    ).replace("hash=", "hash=forged", 1)

    with pytest.raises(TelegramMiniAppInitDataError) as excinfo:
        validate_telegram_mini_app_init_data(
            init_data,
            bot_token=BOT_TOKEN,
            now=now,
        )

    assert excinfo.value.reason == "hash_mismatch"


def test_validate_telegram_mini_app_init_data_rejects_expired_auth_date():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    init_data = _signed_init_data(
        {
            "auth_date": str(int((now - timedelta(days=2)).timestamp())),
            "query_id": "AAEAAAE",
            "user": json.dumps({"id": 42}, separators=(",", ":")),
        }
    )

    with pytest.raises(TelegramMiniAppInitDataError) as excinfo:
        validate_telegram_mini_app_init_data(
            init_data,
            bot_token=BOT_TOKEN,
            max_age_seconds=24 * 60 * 60,
            now=now,
        )

    assert excinfo.value.reason == "auth_date_expired"


def test_validate_telegram_mini_app_init_data_rejects_future_auth_date():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    init_data = _signed_init_data(
        {
            "auth_date": str(int((now + timedelta(minutes=5)).timestamp())),
            "query_id": "AAEAAAE",
            "user": json.dumps({"id": 42}, separators=(",", ":")),
        }
    )

    with pytest.raises(TelegramMiniAppInitDataError) as excinfo:
        validate_telegram_mini_app_init_data(
            init_data,
            bot_token=BOT_TOKEN,
            max_future_skew_seconds=60,
            now=now,
        )

    assert excinfo.value.reason == "auth_date_in_future"


def test_validate_telegram_mini_app_init_data_rejects_duplicate_fields():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    init_data = _signed_init_data(
        {
            "auth_date": str(int(now.timestamp())),
            "query_id": "AAEAAAE",
            "user": json.dumps({"id": 42}, separators=(",", ":")),
        }
    )

    with pytest.raises(TelegramMiniAppInitDataError) as excinfo:
        validate_telegram_mini_app_init_data(
            f"{init_data}&query_id=duplicate",
            bot_token=BOT_TOKEN,
            now=now,
        )

    assert excinfo.value.reason == "duplicate_field"


def test_resolve_telegram_mini_app_session_scope_returns_linked_patient(
    db_session,
    test_patient,
):
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    chat_id = 880101
    db_session.add(_telegram_user(chat_id, patient_id=test_patient.id))
    db_session.commit()
    init_data = _validated_init_data(chat_id, now=now)

    scope = resolve_telegram_mini_app_session_scope(
        db_session,
        init_data,
        expected_scope="patient",
    )

    assert scope.scope_type == "patient"
    assert scope.telegram_chat_id == chat_id
    assert scope.patient_id == test_patient.id
    assert scope.staff_user_id is None
    assert require_telegram_mini_app_patient_scope(
        scope,
        patient_id=test_patient.id,
    ) is scope


def test_resolve_telegram_mini_app_session_scope_returns_active_staff(
    db_session,
    admin_user,
):
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    chat_id = 880102
    db_session.add(_telegram_user(chat_id, user_id=admin_user.id))
    db_session.commit()
    init_data = _validated_init_data(chat_id, now=now)

    scope = resolve_telegram_mini_app_session_scope(
        db_session,
        init_data,
        expected_scope="staff",
    )

    assert scope.scope_type == "staff"
    assert scope.telegram_chat_id == chat_id
    assert scope.staff_user_id == admin_user.id
    assert scope.staff_role == "admin"
    assert scope.patient_id is None
    assert require_telegram_mini_app_staff_scope(
        scope,
        allowed_roles={"Admin"},
    ) is scope


def test_resolve_telegram_mini_app_session_scope_rejects_direct_url_without_user():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    init_data = validate_telegram_mini_app_init_data(
        _signed_init_data(
            {
                "auth_date": str(int(now.timestamp())),
                "query_id": "AAEAAAE",
            }
        ),
        bot_token=BOT_TOKEN,
        now=now,
    )

    with pytest.raises(TelegramMiniAppSessionScopeError) as excinfo:
        resolve_telegram_mini_app_session_scope(None, init_data)

    assert excinfo.value.reason == "telegram_user_required"


def test_resolve_telegram_mini_app_session_scope_rejects_unlinked_account(
    db_session,
):
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    init_data = _validated_init_data(880103, now=now)

    with pytest.raises(TelegramMiniAppSessionScopeError) as excinfo:
        resolve_telegram_mini_app_session_scope(db_session, init_data)

    assert excinfo.value.reason == "telegram_link_required"


def test_require_telegram_mini_app_patient_scope_rejects_wrong_patient(
    db_session,
    test_patient,
):
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    chat_id = 880104
    db_session.add(_telegram_user(chat_id, patient_id=test_patient.id))
    db_session.commit()
    init_data = _validated_init_data(chat_id, now=now)
    scope = resolve_telegram_mini_app_session_scope(
        db_session,
        init_data,
        expected_scope="patient",
    )

    with pytest.raises(TelegramMiniAppSessionScopeError) as excinfo:
        require_telegram_mini_app_patient_scope(
            scope,
            patient_id=test_patient.id + 1,
        )

    assert excinfo.value.reason == "patient_scope_mismatch"


def test_resolve_telegram_mini_app_session_scope_rejects_inactive_staff(
    db_session,
):
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    staff_user = User(
        username="inactive_mini_app_staff",
        email="inactive-mini-app-staff@test.com",
        full_name="Inactive Mini App Staff",
        hashed_password="test",
        role="Doctor",
        is_active=False,
    )
    db_session.add(staff_user)
    db_session.flush()
    chat_id = 880105
    db_session.add(_telegram_user(chat_id, user_id=staff_user.id))
    db_session.commit()
    init_data = _validated_init_data(chat_id, now=now)

    with pytest.raises(TelegramMiniAppSessionScopeError) as excinfo:
        resolve_telegram_mini_app_session_scope(
            db_session,
            init_data,
            expected_scope="staff",
        )

    assert excinfo.value.reason == "staff_link_inactive"


def test_build_telegram_mini_app_appointment_booking_draft_uses_patient_scope(
    db_session,
    test_patient,
):
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    chat_id = 880106
    db_session.add(_telegram_user(chat_id, patient_id=test_patient.id))
    db_session.commit()
    init_data = _validated_init_data(chat_id, now=now)
    scope = resolve_telegram_mini_app_session_scope(
        db_session,
        init_data,
        expected_scope="patient",
    )

    draft = build_telegram_mini_app_appointment_booking_draft(
        scope,
        patient_id=test_patient.id,
        doctor_id=12,
        appointment_date=date(2026, 5, 20),
        appointment_time="09:30",
        department="Cardiology",
        notes="Mini App request",
        services=["Consultation"],
        today=date(2026, 5, 19),
    )

    payload = draft.to_appointment_create_payload()
    assert payload["patient_id"] == test_patient.id
    assert payload["doctor_id"] == 12
    assert payload["appointment_date"] == date(2026, 5, 20)
    assert payload["appointment_time"] == "09:30"
    assert payload["status"] == "scheduled"
    assert payload["visit_type"] == "paid"
    assert payload["payment_type"] == "cash"
    assert payload["payment_currency"] == "UZS"
    assert payload["payment_provider"] is None
    assert payload["payment_transaction_id"] is None
    assert payload["services"] == ["Consultation"]


def test_build_telegram_mini_app_appointment_booking_preview_is_non_mutating(
    db_session,
    test_patient,
):
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    chat_id = 880110
    db_session.add(_telegram_user(chat_id, patient_id=test_patient.id))
    db_session.commit()
    init_data = _validated_init_data(chat_id, now=now)
    scope = resolve_telegram_mini_app_session_scope(
        db_session,
        init_data,
        expected_scope="patient",
    )

    preview = build_telegram_mini_app_appointment_booking_preview(
        scope,
        patient_id=test_patient.id,
        doctor_id=12,
        appointment_date=date(2026, 5, 20),
        appointment_time="09:30",
        department="Cardiology",
        notes="Mini App request",
        services=["Consultation"],
        today=date(2026, 5, 19),
    )

    payload = preview.to_response_payload()
    appointment = payload["appointment"]
    assert payload["preview_only"] is True
    assert payload["mutation_allowed"] is False
    assert payload["message_key"] == "telegram_mini_app_booking_preview_ready"
    assert payload["scope"] == {"type": "patient", "patient_id": test_patient.id}
    assert "appointment_id" not in appointment
    assert appointment["patient_id"] == test_patient.id
    assert appointment["status"] == "scheduled"
    assert appointment["payment_type"] == "cash"
    assert appointment["payment_currency"] == "UZS"
    assert appointment["payment_provider"] is None
    assert appointment["payment_transaction_id"] is None
    assert appointment["payment_webhook_id"] is None


def test_build_telegram_mini_app_appointment_booking_draft_rejects_staff_scope(
    db_session,
    admin_user,
):
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    chat_id = 880107
    db_session.add(_telegram_user(chat_id, user_id=admin_user.id))
    db_session.commit()
    init_data = _validated_init_data(chat_id, now=now)
    scope = resolve_telegram_mini_app_session_scope(
        db_session,
        init_data,
        expected_scope="staff",
    )

    with pytest.raises(TelegramMiniAppSessionScopeError) as excinfo:
        build_telegram_mini_app_appointment_booking_draft(
            scope,
            appointment_date=date(2026, 5, 20),
            today=date(2026, 5, 19),
        )

    assert excinfo.value.reason == "patient_scope_required"


def test_build_telegram_mini_app_appointment_booking_preview_rejects_staff_scope(
    db_session,
    admin_user,
):
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    chat_id = 880111
    db_session.add(_telegram_user(chat_id, user_id=admin_user.id))
    db_session.commit()
    init_data = _validated_init_data(chat_id, now=now)
    scope = resolve_telegram_mini_app_session_scope(
        db_session,
        init_data,
        expected_scope="staff",
    )

    with pytest.raises(TelegramMiniAppSessionScopeError) as excinfo:
        build_telegram_mini_app_appointment_booking_preview(
            scope,
            appointment_date=date(2026, 5, 20),
            today=date(2026, 5, 19),
        )

    assert excinfo.value.reason == "patient_scope_required"


def test_build_telegram_mini_app_appointment_booking_draft_rejects_wrong_patient(
    db_session,
    test_patient,
):
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    chat_id = 880108
    db_session.add(_telegram_user(chat_id, patient_id=test_patient.id))
    db_session.commit()
    init_data = _validated_init_data(chat_id, now=now)
    scope = resolve_telegram_mini_app_session_scope(
        db_session,
        init_data,
        expected_scope="patient",
    )

    with pytest.raises(TelegramMiniAppSessionScopeError) as excinfo:
        build_telegram_mini_app_appointment_booking_draft(
            scope,
            patient_id=test_patient.id + 1,
            appointment_date=date(2026, 5, 20),
            today=date(2026, 5, 19),
        )

    assert excinfo.value.reason == "patient_scope_mismatch"


def test_build_telegram_mini_app_appointment_booking_draft_rejects_unsafe_fields(
    db_session,
    test_patient,
):
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    chat_id = 880109
    db_session.add(_telegram_user(chat_id, patient_id=test_patient.id))
    db_session.commit()
    init_data = _validated_init_data(chat_id, now=now)
    scope = resolve_telegram_mini_app_session_scope(
        db_session,
        init_data,
        expected_scope="patient",
    )

    with pytest.raises(TelegramMiniAppSessionScopeError) as past_exc:
        build_telegram_mini_app_appointment_booking_draft(
            scope,
            appointment_date=date(2026, 5, 18),
            today=date(2026, 5, 19),
        )
    assert past_exc.value.reason == "appointment_date_in_past"

    with pytest.raises(TelegramMiniAppSessionScopeError) as time_exc:
        build_telegram_mini_app_appointment_booking_draft(
            scope,
            appointment_date=date(2026, 5, 20),
            appointment_time="25:99",
            today=date(2026, 5, 19),
        )
    assert time_exc.value.reason == "appointment_time_invalid"
