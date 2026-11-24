"""Link a Telegram profile to a verified patient within the caller's transaction."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.services.patient_subject_lock import lock_patient_subject


class TelegramPatientLinkConflict(Exception):
    def __init__(self, reason: str = "telegram_patient_link_conflict") -> None:
        super().__init__(reason)
        self.reason = reason


def lock_telegram_patient_target(db: Session, patient_id: int) -> None:
    """Serialize verified associations to the same active patient."""
    # NO KEY UPDATE also allows concurrent FK key-share checks.
    patient = db.scalar(
        select(Patient.id)
        .where(Patient.id == patient_id, Patient.is_deleted.is_not(True))
        .with_for_update(key_share=True)
    )
    if patient is None:
        raise TelegramPatientLinkConflict()


def link_telegram_patient(
    db: Session,
    *,
    patient_id: int,
    chat_id: int,
    expected_telegram_user_id: int | None = None,
    create_missing_profile: Callable[[], TelegramUser] | None = None,
    use_confirmation_subject_lock: bool = False,
) -> TelegramUser:
    """Require verified proof from the caller and leave commit or rollback to it."""
    if chat_id <= 0:
        raise TelegramPatientLinkConflict()

    if use_confirmation_subject_lock:
        if not lock_patient_subject(db, patient_id):
            raise TelegramPatientLinkConflict()
    else:
        lock_telegram_patient_target(db, patient_id)

    locked_chat = (
        select(TelegramUser)
        .where(TelegramUser.chat_id == chat_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    profile = db.scalar(locked_chat)
    if profile is None and create_missing_profile is not None:
        create_missing_profile()
        profile = db.scalar(locked_chat)
    if profile is None or (
        expected_telegram_user_id is not None
        and profile.id != expected_telegram_user_id
    ):
        raise TelegramPatientLinkConflict("telegram_user_not_found")
    if not profile.active or profile.blocked:
        raise TelegramPatientLinkConflict()

    if profile.patient_id == patient_id:
        return profile
    if profile.patient_id is not None:
        raise TelegramPatientLinkConflict()

    # The patient lock protects this check against competing verified writes.
    other_profile = db.scalar(
        select(TelegramUser.id)
        .where(
            TelegramUser.patient_id == patient_id,
            TelegramUser.id != profile.id,
            TelegramUser.active.is_(True),
            TelegramUser.blocked.is_(False),
        )
        .limit(1)
    )
    if other_profile is not None:
        raise TelegramPatientLinkConflict()

    profile.patient_id = patient_id
    db.flush()
    return profile
