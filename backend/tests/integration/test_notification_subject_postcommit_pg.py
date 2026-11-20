"""Real nonowner inbox commit cannot authorize a stale outbound push."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.authentication import TokenBlacklist
from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import (
    UserNotificationSettings,
    UserPreferences,
    UserProfile,
)
from app.services.notification_platform_service import NotificationPlatformService
from app.services.notification_subject_intent_service import (
    dispatch_patient_notification_intent,
)
from app.services.notifications_pkg import NotificationSenderService
from tests.integration.test_notification_subject_transfer_pg import (
    notification_pg_engine as notification_pg_engine,
)
from tests.integration.test_notification_subject_transfer_sqlite import _intent, _seed


@pytest.mark.parametrize("change", [
    "none", "logout", "transfer", "hidden_jti", "optout", "hidden_optout",
    "reminder_enabled", "reminder_disabled", "confirmation_enabled", "confirmation_disabled",
    "payment_enabled", "payment_disabled",
])
def test_nonowner_real_sender_rechecks_after_inbox_commit(notification_pg_engine, monkeypatch, change, caplog):
    import app.db.session as session_module
    import app.services.notification_subject_intent_service as subject_service

    owner, runtime = notification_pg_engine
    db_errors = []

    @event.listens_for(runtime, "handle_error")
    def observe_error(context):
        diag = getattr(context.original_exception, "diag", None)
        db_errors.append((getattr(context.original_exception, "sqlstate", None),
                          getattr(diag, "message_primary", None)))

    schema = owner.dialect.default_schema_name
    login = runtime.url.username
    with owner.begin() as conn:
        for table in ("notification_events", "notification_deliveries", "notification_history"):
            conn.exec_driver_sql(f'ALTER TABLE "{schema}"."{table}" ENABLE ROW LEVEL SECURITY')
            conn.exec_driver_sql(f'ALTER TABLE "{schema}"."{table}" FORCE ROW LEVEL SECURITY')
            conn.exec_driver_sql(f'GRANT SELECT, INSERT, UPDATE ON "{schema}"."{table}" TO "{login}"')
            conn.exec_driver_sql(f'CREATE POLICY synthetic_notify_inbox ON "{schema}"."{table}" FOR ALL TO "{login}" USING (true) WITH CHECK (true)')
        conn.exec_driver_sql(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{login}"')
        conn.exec_driver_sql(f'ALTER TABLE "{schema}".user_profiles ENABLE ROW LEVEL SECURITY')
        conn.exec_driver_sql(f'ALTER TABLE "{schema}".user_profiles FORCE ROW LEVEL SECURITY')
        conn.exec_driver_sql(f'GRANT SELECT ON "{schema}".user_profiles TO "{login}"')
        conn.exec_driver_sql(f'CREATE POLICY synthetic_notify_profile ON "{schema}".user_profiles FOR SELECT TO "{login}" USING (true)')
    bearer, patient_id, _, visit_id, payment_id = _seed(owner, contacts=False)
    purpose, field = {
        "reminder": ("appointment_reminder", "push_appointment_reminder"),
        "confirmation": ("visit_confirmation", "push_appointment_confirmation"),
        "payment": ("payment_notification", "push_payment_receipt"),
    }.get(change.rsplit("_", 1)[0], ("visit_confirmation", None))
    with Session(owner) as db:
        patient = db.get(Patient, patient_id)
        user = db.get(User, patient.user_id)
        user.device_token = "synthetic-device"
        user.push_notifications_enabled = True
        subject_user_id = user.id
        if field:
            profile = UserProfile(user_id=user.id)
            db.add(profile)
            db.flush()
            db.add(UserNotificationSettings(
                user_id=user.id, profile_id=profile.id, **{field: change.endswith("_enabled")}
            ))
        other = User(username="synthetic-owner-" + uuid4().hex, hashed_password="!", role="Patient", is_active=True)
        db.add(other)
        db.flush()
        other_id = other.id
        db.commit()
    sender = NotificationSenderService()
    sender.fcm_service = SimpleNamespace(active=True, send_notification=AsyncMock(
        return_value=SimpleNamespace(success=True, error_code=None)))
    broadcasts = AsyncMock(return_value=True)
    commits = []

    def platform_for(db):
        platform = NotificationPlatformService(db)
        platform._broadcast_delivery_with_policy = broadcasts
        commit = platform.repository.commit

        def commit_then_change():
            commit()
            commits.append("inbox")
            if change == "logout":
                with Session(owner) as other:
                    other.add(TokenBlacklist(jti=bearer.jti, user_id=bearer.user_id,
                                             expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
                    other.commit()
            elif change == "transfer":
                with Session(owner) as other:
                    other.get(Patient, patient_id).user_id = other_id
                    other.commit()
            elif change == "hidden_jti":
                with owner.begin() as other:
                    other.exec_driver_sql(f'ALTER POLICY synthetic_subject_select ON "{schema}".token_blacklist USING (false)')
            elif change in {"optout", "hidden_optout"}:
                with Session(owner) as other:
                    profile = UserProfile(user_id=subject_user_id)
                    other.add(profile)
                    other.flush()
                    other.add(UserPreferences(user_id=subject_user_id, profile_id=profile.id, push_notifications=False))
                    other.commit()
                if change == "hidden_optout":
                    with owner.begin() as other:
                        other.exec_driver_sql(f'ALTER POLICY synthetic_notify_preference ON "{schema}".user_preferences USING (false)')

        platform.repository.commit = commit_then_change
        return platform

    sender._platform_service = platform_for
    monkeypatch.setattr(subject_service, "notification_sender_service", sender)
    monkeypatch.setattr(session_module, "SessionLocal", lambda: Session(runtime))
    intent = _intent(runtime, bearer, visit_id, purpose=purpose, payment_id=payment_id)
    asyncio.run(dispatch_patient_notification_intent(intent))
    assert commits == ["inbox"], (db_errors, [(record.message, getattr(record, "error_type", None)) for record in caplog.records])
    if change == "none" or change.endswith("_enabled"):
        broadcasts.assert_awaited_once()
        sender.fcm_service.send_notification.assert_awaited_once()
        sent = str(sender.fcm_service.send_notification.await_args)
        assert "123.45" not in sent and "synthetic-token" not in sent
        assert purpose not in sent
        assert sender.fcm_service.send_notification.await_args.kwargs["data"] == {"type": "notification"}
    elif change == "optout" or change.endswith("_disabled"):
        broadcasts.assert_awaited_once()
        sender.fcm_service.send_notification.assert_not_awaited()
    else:
        broadcasts.assert_not_awaited()
        sender.fcm_service.send_notification.assert_not_awaited()
