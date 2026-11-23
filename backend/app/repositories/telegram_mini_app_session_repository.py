"""Persistence and lock ordering for Telegram patient session credentials."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.models.telegram_mini_app_session import TelegramMiniAppSession


class TelegramMiniAppSessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, session_id: str) -> TelegramMiniAppSession | None:
        return self.db.execute(
            select(TelegramMiniAppSession)
            .where(TelegramMiniAppSession.id == session_id)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()

    def lock_patient(self, patient_id: int) -> None:
        # All credential mutations use patient -> session ordering to prevent
        # two devices revoking each other from deadlocking.
        # NO KEY UPDATE also permits a link writer's patient FK KEY SHARE,
        # avoiding a patient/link lock cycle when an exchange locks the link.
        self.db.execute(
            select(Patient.id)
            .where(Patient.id == patient_id)
            .with_for_update(key_share=True)
        ).first()

    def lock_patient_link_epoch(
        self, *, telegram_user_id: int, patient_id: int, chat_id: int
    ) -> int | None:
        # Lock the patient first, then hold this link only until exchange commits.
        # A scalar read bypasses any stale TelegramUser in the identity map.
        return self.db.execute(
            select(TelegramUser.patient_link_epoch)
            .join(Patient, Patient.id == TelegramUser.patient_id)
            .where(
                TelegramUser.id == telegram_user_id,
                TelegramUser.patient_id == patient_id,
                TelegramUser.chat_id == chat_id,
                TelegramUser.active.is_(True),
                TelegramUser.blocked.is_(False),
                Patient.is_deleted.is_(False),
            )
            .with_for_update(of=TelegramUser)
        ).scalar_one_or_none()

    def active_context(
        self,
        session_id: str,
        now: datetime,
    ) -> tuple[TelegramMiniAppSession, int] | None:
        return self.db.execute(
            select(TelegramMiniAppSession, TelegramUser.chat_id)
            .join(
                TelegramUser, TelegramUser.id == TelegramMiniAppSession.telegram_user_id
            )
            .join(Patient, Patient.id == TelegramMiniAppSession.patient_id)
            .where(
                TelegramMiniAppSession.id == session_id,
                TelegramMiniAppSession.revoked_at.is_(None),
                TelegramMiniAppSession.expires_at > now,
                TelegramUser.patient_id == TelegramMiniAppSession.patient_id,
                TelegramUser.patient_link_epoch
                == TelegramMiniAppSession.patient_link_epoch,
                TelegramUser.active.is_(True),
                TelegramUser.blocked.is_(False),
                Patient.is_deleted.is_(False),
            )
            .execution_options(populate_existing=True)
        ).first()

    def list_active(
        self, patient_id: int, now: datetime
    ) -> list[TelegramMiniAppSession]:
        return list(
            self.db.scalars(
                select(TelegramMiniAppSession)
                .join(
                    TelegramUser,
                    TelegramUser.id == TelegramMiniAppSession.telegram_user_id,
                )
                .where(
                    TelegramMiniAppSession.patient_id == patient_id,
                    TelegramMiniAppSession.revoked_at.is_(None),
                    TelegramMiniAppSession.expires_at > now,
                    TelegramUser.patient_id == patient_id,
                    TelegramUser.patient_link_epoch
                    == TelegramMiniAppSession.patient_link_epoch,
                    TelegramUser.active.is_(True),
                    TelegramUser.blocked.is_(False),
                )
                .order_by(
                    TelegramMiniAppSession.created_at.desc(), TelegramMiniAppSession.id
                )
            )
        )

    def revoke_others(self, patient_id: int, current_id: str, now: datetime) -> int:
        result = self.db.execute(
            update(TelegramMiniAppSession)
            .where(
                TelegramMiniAppSession.patient_id == patient_id,
                TelegramMiniAppSession.id != current_id,
                TelegramMiniAppSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        return result.rowcount

    def add(self, row: TelegramMiniAppSession) -> None:
        self.db.add(row)

    def init_data_exchanged(self, digest: str) -> bool:
        return (
            self.db.execute(
                select(TelegramMiniAppSession.id).where(
                    TelegramMiniAppSession.init_data_hash == digest
                )
            ).first()
            is not None
        )
