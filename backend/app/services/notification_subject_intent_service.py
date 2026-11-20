"""Patient notification intents bound to a Visit, not captured clinical content.

Only neutral channel messages are emitted. This does not implement the wider
inbox ownership fence or authorize user-data transfer.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.roles import is_doctor_role_spelling
from app.db.trusted_schema import (
    TrustedSchemaUnavailable,
    _approved_roles,
    _check_owner_members,
    _identifier,
    _names,
)
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.telegram_config import TelegramUser
from app.models.user import User
from app.models.user_profile import UserNotificationSettings, UserPreferences
from app.models.visit import Visit
from app.services.notifications import notification_sender_service
from app.services.notifications_pkg._helpers import (
    _is_private_telegram_chat_id,
    _patient_telegram_preferences_enabled,
    neutral_patient_notice,
)
from app.services.patient_subject_lock import (
    PatientSubjectLockError,
    lock_patient_subject,
    require_patient_subject_visibility,
)
from app.services.profile_contact_security import (
    ProfileBearerContext,
    ProfileBearerInvalid,
    check_bearer_expiry,
    check_profile_bearer,
)

logger = logging.getLogger(__name__)
Purpose = Literal["appointment_reminder", "visit_confirmation", "payment_notification"]


@dataclass(frozen=True, repr=False)
class PatientNotificationIntent:
    purpose: Purpose
    visit_id: int
    patient_id: int
    visit_epoch: int
    actor_role: str
    actor_superuser: bool
    doctor_id: int | None
    doctor_generation: int | None
    payment_id: int | None
    eligible_channels: tuple[str, ...]
    bearer: ProfileBearerContext


def _require_revocable_bearer(bearer: ProfileBearerContext) -> None:
    if (not isinstance(bearer, ProfileBearerContext) or bearer.patient_id is not None
        or not isinstance(bearer.jti, str) or not bearer.jti
        or type(bearer.expires_at) is not int):
        raise ProfileBearerInvalid("Bearer session unavailable")
    check_bearer_expiry(bearer)


def _require_preference_visibility(db: Session) -> None:
    """Prove absent opt-outs really are absent for this locked transaction."""
    dialect = db.get_bind().dialect
    if dialect.name == "sqlite":
        return
    if dialect.name != "postgresql":
        raise PatientSubjectLockError(status_code=503, detail="Уведомление временно недоступно")
    try:
        schema = _identifier(settings.TRUSTED_DB_SCHEMA)
        owner = _identifier(settings.NOTIFY_PREFERENCES_DB_OWNER)
        runtime = _identifier(settings.TRUSTED_DB_RUNTIME_ROLE)
        owner_members = _names(settings.NOTIFY_PREFERENCES_DB_OWNER_MEMBERS)
        readers = _names(settings.NOTIFY_PREFERENCES_DB_READ_ROLES)
        writers = _names(settings.NOTIFY_PREFERENCES_DB_WRITE_ROLES)
        if owner == runtime:
            raise TrustedSchemaUnavailable("Preference visibility unavailable")
        quote = dialect.identifier_preparer.quote_identifier
        tables = ("user_preferences", "user_notification_settings")
        qualified = [f"{quote(schema)}.{quote(name)}" for name in tables]
        db.execute(text("LOCK TABLE " + ", ".join(qualified) + " IN ACCESS SHARE MODE"))
        runtime_oid = db.execute(text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname=:runtime"),
                                 {"runtime": runtime}).scalar_one_or_none()
        if runtime_oid is None:
            raise TrustedSchemaUnavailable("Preference visibility unavailable")
        for name in tables:
            relation = db.execute(text("""
              SELECT c.oid,c.relowner,c.relkind,c.relrowsecurity,r.rolname AS owner_name,
                pg_catalog.has_table_privilege(:runtime,c.oid,'SELECT') AS can_select,
                pg_catalog.has_any_column_privilege(:runtime,c.oid,'UPDATE') AS can_lock,
                EXISTS(SELECT 1 FROM pg_catalog.pg_inherits i WHERE i.inhrelid=c.oid OR i.inhparent=c.oid) AS inherited
              FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
              WHERE n.nspname=:schema AND c.relname=:name
            """), {"runtime": runtime_oid, "schema": schema, "name": name}).mappings().first()
            if (relation is None or relation["relkind"] != "r" or relation["inherited"]
                or relation["owner_name"] != owner or relation["relowner"] == runtime_oid
                or not relation["can_select"] or not relation["can_lock"]):
                raise TrustedSchemaUnavailable("Preference visibility unavailable")
            integrity = db.execute(text("""
              SELECT pg_catalog.current_setting('session_replication_role')='origin'
                AND EXISTS (
                  SELECT 1 FROM pg_catalog.pg_constraint fk
                    JOIN pg_catalog.pg_attribute child ON child.attrelid=fk.conrelid AND child.attname='user_id' AND NOT child.attisdropped
                    JOIN pg_catalog.pg_attribute parent ON parent.attrelid=fk.confrelid AND parent.attname='id' AND NOT parent.attisdropped
                  WHERE fk.contype='f' AND fk.conrelid=:oid AND fk.confrelid=pg_catalog.to_regclass(:users)
                    AND fk.convalidated AND fk.conkey=ARRAY[child.attnum]::pg_catalog.int2[]
                    AND fk.confkey=ARRAY[parent.attnum]::pg_catalog.int2[]
                    AND (SELECT count(*) FROM pg_catalog.pg_trigger t WHERE t.tgconstraint=fk.oid AND t.tgrelid=fk.conrelid)=2
                    AND (SELECT count(*) FROM pg_catalog.pg_trigger t WHERE t.tgconstraint=fk.oid AND t.tgrelid=fk.confrelid)=2
                    AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_trigger t WHERE t.tgconstraint=fk.oid AND t.tgenabled NOT IN ('O','A'))
                ) AND EXISTS (
                  SELECT 1 FROM pg_catalog.pg_index i JOIN pg_catalog.pg_attribute a
                    ON a.attrelid=i.indrelid AND a.attname='user_id' AND NOT a.attisdropped
                  WHERE i.indrelid=:oid AND i.indisunique AND i.indisvalid AND i.indisready
                    AND i.indpred IS NULL AND i.indexprs IS NULL AND i.indnkeyatts=1 AND i.indkey[0]=a.attnum
                )
            """), {"oid": relation["oid"], "users": f"{quote(schema)}.users"}).scalar_one()
            if integrity is not True:
                raise TrustedSchemaUnavailable("Preference visibility unavailable")
            _check_owner_members(db, relation["relowner"], owner_members)
            approved = _approved_roles(db, owner_oid=relation["relowner"], owner_name=owner,
                owner_members=owner_members, runtime_oid=runtime_oid, runtime_name=runtime,
                role_groups=(readers, writers))
            grants = db.execute(text("""
              SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_class c,
                LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
              WHERE c.oid=:oid AND a.grantee<>c.relowner
              UNION ALL
              SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_attribute col,
                LATERAL pg_catalog.aclexplode(col.attacl) a
              WHERE col.attrelid=:oid AND col.attnum>0 AND NOT col.attisdropped AND a.grantee<>:owner
            """), {"oid": relation["oid"], "owner": relation["relowner"]}).all()
            allowed_readers = {runtime_oid, *(approved[name] for name in readers)}
            allowed_writers = {runtime_oid, *(approved[name] for name in writers)}
            if any(grant.is_grantable or (
                grant.grantee not in allowed_readers if grant.privilege_type == "SELECT" else
                grant.privilege_type not in {"INSERT", "UPDATE", "DELETE"} or grant.grantee not in allowed_writers
            ) for grant in grants):
                raise TrustedSchemaUnavailable("Preference visibility unavailable")
            if relation["relrowsecurity"]:
                for command in ("r", "w"):
                    policies = db.execute(text("""
                      SELECT p.polpermissive,pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS predicate
                      FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid AND p.polcmd IN (:command,'*')
                        AND (0=ANY(p.polroles) OR :runtime=ANY(p.polroles))
                    """), {"oid": relation["oid"], "runtime": runtime_oid, "command": command}).mappings().all()
                    if (any(not policy["polpermissive"] for policy in policies)
                        or not any(policy["polpermissive"] and policy["predicate"] == "true" for policy in policies)):
                        raise TrustedSchemaUnavailable("Preference visibility unavailable")
    except (DBAPIError, TrustedSchemaUnavailable, TypeError, ValueError):
        db.rollback()
        raise PatientSubjectLockError(status_code=503, detail="Уведомление временно недоступно") from None


def _admin(actor: User) -> bool:
    return bool(actor.is_superuser) or str(actor.role or "").strip().lower() == "admin"


def _doctor(db: Session, actor: User, visit: Visit, *, lock: bool) -> Doctor | None:
    if _admin(actor):
        return None
    if not is_doctor_role_spelling(actor.role):
        raise HTTPException(status_code=404, detail="Визит не найден")
    query = db.query(Doctor).filter(Doctor.user_id == actor.id, Doctor.active.is_(True))
    if lock:
        query = query.with_for_update(of=Doctor).populate_existing()
    doctor = query.first()
    if (
        doctor is None
        or doctor.id != visit.doctor_id
        or not doctor.repeat_owner_generation
    ):
        raise HTTPException(status_code=404, detail="Визит не найден")
    return doctor


def _paid_payment(
    db: Session, payment_id: int | None, visit_id: int, *, lock: bool
) -> Payment:
    if payment_id is None:
        raise HTTPException(status_code=409, detail="Укажите подтверждённый платёж")
    query = db.query(Payment).filter(Payment.id == payment_id)
    if lock:
        query = query.with_for_update(of=Payment).populate_existing()
    payment = query.first()
    if (
        payment is None
        or payment.visit_id != visit_id
        or str(payment.status or "").lower() not in {"paid", "completed"}
    ):
        raise HTTPException(
            status_code=409, detail="Платёж не подтверждён для этого визита"
        )
    try:
        amount = Decimal(str(payment.amount))
        refunded = Decimal(str(payment.refunded_amount or 0))
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(
            status_code=409, detail="Состояние платежа требует сверки"
        ) from None
    if (
        not amount.is_finite()
        or not refunded.is_finite()
        or amount <= 0
        or refunded < 0
        or refunded >= amount
    ):
        raise HTTPException(status_code=409, detail="Состояние платежа требует сверки")
    return payment


def _portal_user(db: Session, patient: Patient) -> User | None:
    if patient.user_id is None:
        return None
    user = db.query(User).filter(User.id == patient.user_id).populate_existing().first()
    if (
        user is None
        or not user.is_active
        or user.is_superuser
        or str(user.role or "").strip().lower() != "patient"
    ):
        return None
    return user


def _eligible_channels(
    db: Session, patient: Patient, purpose: Purpose
) -> tuple[str, ...]:
    channels = []
    if _portal_user(db, patient) is not None:
        channels.append("inbox")
    sender = notification_sender_service
    for channel, contact in (("email", patient.email), ("sms", patient.phone)):
        if contact and sender._patient_channel_opted_in(
            db=db, patient_id=patient.id, channel=channel, event_type=purpose
        ):
            channels.append(channel)
    telegram = (
        db.query(TelegramUser)
        .filter(
            TelegramUser.patient_id == patient.id,
            TelegramUser.active.is_(True),
            TelegramUser.blocked.is_(False),
        )
        .order_by(TelegramUser.id.desc())
        .first()
    )
    if (
        telegram
        and _is_private_telegram_chat_id(telegram.chat_id)
        and _patient_telegram_preferences_enabled(telegram, purpose)
        # Legacy links lack evidence binding the chat to the current owner.
        # The 0124 rollout must supply and verify this snapshot before the
        # Telegram path can be enabled for a transferred subject.
        and getattr(telegram, "patient_owner_generation_snapshot", None)
        == patient.notification_owner_generation
    ):
        channels.append("telegram")
    return tuple(channels)


def create_patient_notification_intent(
    db: Session,
    *,
    bearer: ProfileBearerContext,
    purpose: Purpose,
    visit_id: int,
    requested_patient_id: int | None = None,
    payment_id: int | None = None,
) -> PatientNotificationIntent:
    if purpose not in {
        "appointment_reminder",
        "visit_confirmation",
        "payment_notification",
    }:
        raise HTTPException(status_code=422, detail="Неизвестный тип уведомления")
    try:
        # Prove full blacklist and subject visibility before reading the actor
        # or treating a missing revocation record as an authorized session.
        require_patient_subject_visibility(db)
        _require_preference_visibility(db)
    except PatientSubjectLockError as exc:
        raise HTTPException(status_code=exc.status_code, detail="Уведомление временно недоступно") from None
    try:
        _require_revocable_bearer(bearer)
        actor = db.query(User).filter(User.id == bearer.user_id).populate_existing().first()
        if actor is None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        check_profile_bearer(db, actor, bearer)
    except ProfileBearerInvalid as exc:
        raise HTTPException(status_code=403, detail="Доступ запрещён") from exc
    visit = db.query(Visit).filter(Visit.id == visit_id).populate_existing().first()
    if visit is None or (
        requested_patient_id is not None and visit.patient_id != requested_patient_id
    ):
        raise HTTPException(status_code=404, detail="Визит не найден")
    doctor = _doctor(db, actor, visit, lock=False)
    patient = (
        db.query(Patient)
        .filter(Patient.id == visit.patient_id)
        .populate_existing()
        .first()
    )
    if patient is None or patient.is_deleted:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    epoch = visit.confirmation_context_epoch
    if not isinstance(epoch, int) or epoch <= 0:
        raise HTTPException(status_code=409, detail="Контекст визита требует сверки")
    if purpose == "payment_notification":
        _paid_payment(db, payment_id, visit.id, lock=False)
    channels = _eligible_channels(db, patient, purpose)
    if not channels:
        raise HTTPException(
            status_code=409, detail="Нет доступного разрешённого канала уведомлений"
        )
    return PatientNotificationIntent(
        purpose=purpose,
        visit_id=visit.id,
        patient_id=patient.id,
        visit_epoch=epoch,
        actor_role=str(actor.role or ""),
        actor_superuser=bool(actor.is_superuser),
        doctor_id=doctor.id if doctor else None,
        doctor_generation=doctor.repeat_owner_generation if doctor else None,
        payment_id=payment_id if purpose == "payment_notification" else None,
        eligible_channels=channels,
        bearer=bearer,
    )


def _lock_current_intent(db: Session, intent: PatientNotificationIntent):
    """Pin each transaction, then lock and recheck issuer and exact subject."""
    require_patient_subject_visibility(db)
    _require_preference_visibility(db)
    _require_revocable_bearer(intent.bearer)
    if db.get_bind().dialect.name == "sqlite":
        db.connection().exec_driver_sql("UPDATE users SET id=id WHERE 0")
    hint = db.query(Patient.user_id).filter(Patient.id == intent.patient_id).first()
    if hint is None:
        raise ProfileBearerInvalid("Subject unavailable")
    user_ids = sorted({value for value in (intent.bearer.user_id, hint.user_id) if value is not None})
    users = (db.query(User).filter(User.id.in_(user_ids)).order_by(User.id)
             .with_for_update(of=User).populate_existing().all())
    by_id = {user.id: user for user in users}
    actor = by_id.get(intent.bearer.user_id)
    if (actor is None or str(actor.role or "") != intent.actor_role
        or bool(actor.is_superuser) != intent.actor_superuser):
        raise ProfileBearerInvalid("Issuer unavailable")
    if hint.user_id is not None and hint.user_id not in by_id:
        raise ProfileBearerInvalid("Subject unavailable")
    check_profile_bearer(db, actor, intent.bearer)
    doctor = None
    if intent.doctor_id is not None:
        doctor = (db.query(Doctor).filter(Doctor.id == intent.doctor_id)
                  .with_for_update(of=Doctor).populate_existing().first())
        if (doctor is None or not doctor.active or doctor.user_id != actor.id
            or doctor.repeat_owner_generation != intent.doctor_generation):
            raise ProfileBearerInvalid("Issuer unavailable")
    elif not _admin(actor):
        raise ProfileBearerInvalid("Issuer unavailable")
    if not lock_patient_subject(db, intent.patient_id):
        raise ProfileBearerInvalid("Subject unavailable")
    patient = db.query(Patient).filter(Patient.id == intent.patient_id).populate_existing().first()
    visit = (db.query(Visit).filter(Visit.id == intent.visit_id).with_for_update(of=Visit)
             .populate_existing().first())
    if (patient is None or patient.is_deleted or patient.user_id != hint.user_id
        or visit is None or visit.patient_id != patient.id or visit.confirmation_context_epoch != intent.visit_epoch
        or (doctor is not None and visit.doctor_id != doctor.id)):
        raise ProfileBearerInvalid("Subject unavailable")
    if intent.purpose == "payment_notification":
        _paid_payment(db, intent.payment_id, visit.id, lock=True)
    if patient.user_id is not None:
        # User FOR UPDATE fences insertion of missing FK-backed rows; lock
        # existing rows NOWAIT so a concurrent opt-out cannot be missed.
        for model in (UserPreferences, UserNotificationSettings):
            (db.query(model.id).filter(model.user_id == patient.user_id)
             .order_by(model.id).with_for_update(nowait=True).all())
    channels = _eligible_channels(db, patient, intent.purpose)
    portal = _portal_user(db, patient)
    check_bearer_expiry(intent.bearer)
    return patient, channels, portal.id if portal else None


async def dispatch_patient_notification_intent(
    intent: PatientNotificationIntent,
) -> None:
    """Revalidate each transaction; only neutral information leaves the app.

    A provider request already accepted cannot be recalled. We never retry an
    uncertain external outcome or proceed to later channels after such a result.
    """
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        patient, channels, portal_user_id = _lock_current_intent(db, intent)
        email, phone = patient.email, patient.phone
        db.commit()
        neutral_message = neutral_patient_notice(has_portal=portal_user_id is not None)

        async def contact(channel, expected, send):
            if channel not in channels:
                return True
            current, available, current_portal = _lock_current_intent(db, intent)
            if current_portal != portal_user_id:
                raise ProfileBearerInvalid("Subject unavailable")
            if (channel not in available or (channel == "email" and current.email != expected)
                or (channel == "sms" and current.phone != expected)):
                db.rollback()
                return True  # Consent/contact changed; retain other authorized channels.
            check_bearer_expiry(intent.bearer)
            db.commit()
            check_bearer_expiry(intent.bearer)
            return await send()

        if not await contact("email", email, lambda: notification_sender_service.send_email(
            email, "Новое уведомление", neutral_message
        )):
            return
        if not await contact("sms", phone, lambda: notification_sender_service.send_sms(phone, neutral_message)):
            return
        # Telegram remains ineligible for legacy links until 0124 establishes
        # and verifies owner-bound chat evidence and the send-time link fence.
        if "telegram" in channels:
            current, available, current_portal = _lock_current_intent(db, intent)
            if "telegram" not in available or current_portal != portal_user_id:
                raise ProfileBearerInvalid("Subject unavailable")
            check_bearer_expiry(intent.bearer)
            if not await asyncio.wait_for(notification_sender_service.send_patient_telegram_event_notification(
                db=db, patient_id=current.id, event_type=intent.purpose,
                neutral=True, has_portal=portal_user_id is not None,
            ), timeout=15):
                return
            db.commit()
        if portal_user_id is not None and "inbox" in channels:
            _, available, current_portal = _lock_current_intent(db, intent)
            if "inbox" not in available or current_portal != portal_user_id:
                raise ProfileBearerInvalid("Subject unavailable")
            check_bearer_expiry(intent.bearer)
            db.commit()

            def after_inbox_commit():
                try:
                    _, current_channels, current_id = _lock_current_intent(db, intent)
                    if "inbox" not in current_channels or current_id != portal_user_id:
                        raise ProfileBearerInvalid("Subject unavailable")
                    return True
                except (ProfileBearerInvalid, PatientSubjectLockError, HTTPException):
                    db.rollback()
                    return False

            def schema_pin():
                try:
                    require_patient_subject_visibility(db)
                    return True
                except PatientSubjectLockError:
                    db.rollback()
                    return False

            def before_send():
                try:
                    check_bearer_expiry(intent.bearer)
                    return True
                except ProfileBearerInvalid:
                    db.rollback()
                    return False

            check_bearer_expiry(intent.bearer)
            await asyncio.wait_for(notification_sender_service.send_push(
                user_id=portal_user_id, title="Новое уведомление", message=neutral_message,
                data={"type": "notification"}, db=db,
                subject_after_commit=after_inbox_commit, subject_schema_pin=schema_pin,
                subject_before_send=before_send, subject_preference_event_type=intent.purpose,
            ), timeout=15)
    except (ProfileBearerInvalid, PatientSubjectLockError, HTTPException):
        db.rollback()
    except Exception as exc:
        db.rollback()
        logger.warning("Patient notification intent failed: %s", type(exc).__name__)
    finally:
        db.close()
