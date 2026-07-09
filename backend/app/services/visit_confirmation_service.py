"""Service layer for visit confirmation endpoints."""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.core.config import settings
from app.crud import clinic as crud_clinic
from app.crud import telegram_config as crud_telegram
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.visit import Visit
from app.repositories.visit_confirmation_repository import VisitConfirmationRepository
from app.services.confirmation_security import ConfirmationSecurityService
from app.services.context_facades.queue_facade import (
    QueueContextFacade,
    QueueDomainServiceContractAdapter,
)
from app.services.queue_service import queue_service
from app.utils.validators import normalize_phone_uz

logger = logging.getLogger(__name__)

CANONICAL_ACTIVE_CONFIRMATION_STATUSES = (
    "waiting",
    "called",
    "in_service",
    "diagnostics",
)
CONFIRMATION_PROCESSING_STATUS = "confirmation_processing"

TELEGRAM_TICKET_QR_PREFIX = "tq"
TELEGRAM_TICKET_QR_HASH_PREFIX = "ticket_qr:"
TELEGRAM_TICKET_QR_SEPARATOR = "_"
TELEGRAM_TICKET_QR_TTL_MINUTES = 15
TELEGRAM_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")


@dataclass
class VisitConfirmationDomainError(Exception):
    status_code: int
    detail: str
    headers: dict[str, str] | None = None


def _base36_encode(value: int) -> str:
    if value < 0:
        raise ValueError("base36 value must be non-negative")
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = ""
    while value:
        value, remainder = divmod(value, 36)
        result = alphabet[remainder] + result
    return result


def _base36_decode(value: str) -> int:
    return int(value, 36)


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _as_aware_utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime.

    SQLAlchemy ``DateTime(timezone=True)`` columns return aware datetimes on
    PostgreSQL but naive datetimes on SQLite (used by the test suite). Mixing
    naive and aware datetimes in comparisons raises ``TypeError``. Normalize
    every datetime read from the database to aware UTC before comparing with
    ``datetime.now(UTC)``.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _ticket_qr_signature(body: str) -> str:
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _base36_encode(int.from_bytes(digest[:12], "big"))


def _hash_telegram_ticket_start_token(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{TELEGRAM_TICKET_QR_HASH_PREFIX}{digest}"


def build_telegram_ticket_start_token(*, expires_at: datetime, nonce: str | None = None) -> str:
    """Build a compact signed Telegram /start payload without patient data."""
    exp = int(_as_utc_naive(expires_at).replace(tzinfo=UTC).timestamp())
    token_nonce = nonce or _base36_encode(secrets.randbits(48))
    body = (
        f"{TELEGRAM_TICKET_QR_PREFIX}{TELEGRAM_TICKET_QR_SEPARATOR}"
        f"{_base36_encode(exp)}{TELEGRAM_TICKET_QR_SEPARATOR}{token_nonce}"
    )
    return (
        f"{body}{TELEGRAM_TICKET_QR_SEPARATOR}"
        f"{_ticket_qr_signature(body)}"
    )


def parse_telegram_ticket_start_token(token: str) -> dict[str, Any] | None:
    parts = (token or "").split(TELEGRAM_TICKET_QR_SEPARATOR)
    if len(parts) != 4 or parts[0] != TELEGRAM_TICKET_QR_PREFIX:
        return None

    body = TELEGRAM_TICKET_QR_SEPARATOR.join(parts[:3])
    if not hmac.compare_digest(parts[3], _ticket_qr_signature(body)):
        return None

    try:
        expires_at = datetime.fromtimestamp(_base36_decode(parts[1]), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None

    if expires_at < datetime.now(UTC):
        return None

    return {
        "expires_at": expires_at.replace(tzinfo=None),
        "token_hash": _hash_telegram_ticket_start_token(token),
    }


def consume_telegram_ticket_start_token(db, token: str) -> Visit | None:
    """Mark a valid ticket QR token as consumed in the current transaction."""
    parsed = parse_telegram_ticket_start_token(token)
    if not parsed:
        return None

    now = datetime.now(UTC)
    token_hash = parsed["token_hash"]
    visit = db.query(Visit).filter(Visit.confirmation_token == token_hash).first()
    if not visit:
        return None

    if visit.confirmation_expires_at and _as_aware_utc(visit.confirmation_expires_at) < now:
        return None

    updated = (
        db.query(Visit)
        .filter(Visit.id == visit.id, Visit.confirmation_token == token_hash)
        .update(
            {
                "confirmation_token": None,
                "confirmation_expires_at": None,
            },
            synchronize_session=False,
        )
    )
    if updated != 1:
        return None

    return visit


class VisitConfirmationService:
    """Contains confirmation business rules and orchestration."""

    def __init__(self, db):
        self.repository = VisitConfirmationRepository(db)
        self.security_service = ConfirmationSecurityService(db)
        self.queue_facade = QueueContextFacade(QueueDomainServiceContractAdapter(db))

    def _claim_pending_visit_for_confirmation(self, token: str) -> Visit | None:
        updated = (
            self.repository.db.query(Visit)
            .filter(
                Visit.confirmation_token == token,
                Visit.status == "pending_confirmation",
            )
            .update(
                {Visit.status: CONFIRMATION_PROCESSING_STATUS},
                synchronize_session=False,
            )
        )
        if updated == 0:
            return None
        if updated != 1:
            raise VisitConfirmationDomainError(
                status_code=409,
                detail="Ambiguous confirmation token",
            )

        self.repository.db.flush()
        return (
            self.repository.db.query(Visit)
            .filter(
                Visit.confirmation_token == token,
                Visit.status == CONFIRMATION_PROCESSING_STATUS,
            )
            .first()
        )

    def confirm_by_telegram(
        self,
        *,
        token: str,
        telegram_user_id: str | None,
        source_ip: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        visit = None
        try:
            security_check = self.security_service.validate_confirmation_request(
                token=token,
                source_ip=source_ip,
                user_agent=user_agent,
                channel="telegram",
            )

            if not security_check.allowed:
                self.security_service.record_confirmation_attempt(
                    visit_id=0,
                    success=False,
                    channel="telegram",
                    error_reason=security_check.reason,
                )
                if security_check.reason == "Недействительный токен подтверждения":
                    raise VisitConfirmationDomainError(
                        status_code=404,
                        detail="Визит не найден или уже подтвержден",
                    )
                raise VisitConfirmationDomainError(
                    status_code=429 if security_check.retry_after else 400,
                    detail=security_check.reason,
                    headers=(
                        {"Retry-After": str(security_check.retry_after)}
                        if security_check.retry_after
                        else None
                    ),
                )

            visit = self._claim_pending_visit_for_confirmation(token)
            if not visit:
                self.security_service.record_confirmation_attempt(
                    visit_id=0,
                    success=False,
                    channel="telegram",
                    error_reason="Visit not found",
                )
                raise VisitConfirmationDomainError(
                    status_code=404,
                    detail="Визит не найден или уже подтвержден",
                )

            if visit.confirmation_channel not in ["telegram", "auto"]:
                self.security_service.record_confirmation_attempt(
                    visit_id=visit.id,
                    success=False,
                    channel="telegram",
                    error_reason="Wrong confirmation channel",
                )
                raise VisitConfirmationDomainError(
                    status_code=400,
                    detail="Этот визит нельзя подтвердить через Telegram",
                )

            result = self._confirm_visit(
                visit=visit,
                confirmed_by=f"telegram_{telegram_user_id or 'unknown'}",
                channel="telegram",
                confirmation_telegram_id=telegram_user_id,
            )

            self.security_service.record_confirmation_attempt(
                visit_id=visit.id,
                success=True,
                channel="telegram",
            )
            return result
        except VisitConfirmationDomainError:
            self.repository.rollback()
            raise
        except Exception as exc:
            self.repository.rollback()
            try:
                self.security_service.record_confirmation_attempt(
                    visit_id=visit.id if visit else 0,
                    success=False,
                    channel="telegram",
                    error_reason=f"System error: {exc}",
                )
            except Exception:
                pass
            raise VisitConfirmationDomainError(
                status_code=500,
                detail=f"Ошибка подтверждения визита: {exc}",
            ) from exc

    def confirm_by_pwa(
        self,
        *,
        token: str,
        patient_phone: str | None,
        source_ip: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        try:
            security_check = self.security_service.validate_confirmation_request(
                token=token,
                source_ip=source_ip,
                user_agent=user_agent,
                channel="pwa",
            )
            if not security_check.allowed:
                self.security_service.record_confirmation_attempt(
                    visit_id=0,
                    success=False,
                    channel="pwa",
                    error_reason=security_check.reason,
                )
                if security_check.reason == "Недействительный токен подтверждения":
                    raise VisitConfirmationDomainError(
                        status_code=404,
                        detail="Визит не найден или уже подтвержден",
                    )
                raise VisitConfirmationDomainError(
                    status_code=429 if security_check.retry_after else 400,
                    detail=security_check.reason,
                )

            visit = self._claim_pending_visit_for_confirmation(token)
            if not visit:
                self.security_service.record_confirmation_attempt(
                    visit_id=0,
                    success=False,
                    channel="pwa",
                    error_reason="Visit not found",
                )
                raise VisitConfirmationDomainError(
                    status_code=404,
                    detail="Визит не найден или уже подтвержден",
                )

            if (
                visit.confirmation_expires_at
                and _as_aware_utc(visit.confirmation_expires_at) < datetime.now(UTC)
            ):
                raise VisitConfirmationDomainError(
                    status_code=400,
                    detail="Срок подтверждения истек",
                )

            if visit.confirmation_channel not in ["pwa", "auto"]:
                raise VisitConfirmationDomainError(
                    status_code=400,
                    detail="Этот визит нельзя подтвердить через PWA",
                )

            if patient_phone:
                patient = self.repository.get_patient(visit.patient_id)
                if patient and patient.phone and patient.phone != patient_phone:
                    raise VisitConfirmationDomainError(
                        status_code=400,
                        detail="Номер телефона не совпадает с записью",
                    )

            result = self._confirm_visit(
                visit=visit,
                confirmed_by=f"pwa_{source_ip or 'unknown'}",
                channel="pwa",
                confirmation_phone=patient_phone,
            )
            self.security_service.record_confirmation_attempt(
                visit_id=visit.id, success=True, channel="pwa"
            )
            return result
        except VisitConfirmationDomainError:
            self.repository.rollback()
            raise
        except Exception as exc:
            self.repository.rollback()
            raise VisitConfirmationDomainError(
                status_code=500,
                detail=f"Ошибка подтверждения визита: {exc}",
            ) from exc

    def get_visit_info(self, token: str) -> dict[str, Any]:
        try:
            visit = self.repository.get_visit_by_token(token)
            if not visit:
                raise VisitConfirmationDomainError(
                    status_code=404,
                    detail="Визит не найден",
                )

            if (
                visit.confirmation_expires_at
                and _as_aware_utc(visit.confirmation_expires_at) < datetime.now(UTC)
            ):
                raise VisitConfirmationDomainError(
                    status_code=400,
                    detail="Срок подтверждения истек",
                )

            if visit.status != "pending_confirmation":
                raise VisitConfirmationDomainError(
                    status_code=400,
                    detail=f"Визит уже имеет статус: {visit.status}",
                )

            patient = self.repository.get_patient(visit.patient_id)
            visit_services = self.repository.get_visit_services(visit.id)

            services_info = []
            total_amount = 0.0
            for vs in visit_services:
                item_total = float(vs.price * vs.qty) if vs.price else 0.0
                services_info.append(
                    {
                        "name": vs.name,
                        "code": vs.code,
                        "quantity": vs.qty,
                        "price": float(vs.price) if vs.price else 0.0,
                        "total": item_total,
                    }
                )
                total_amount += item_total

            doctor = self.repository.get_doctor(visit.doctor_id) if visit.doctor_id else None
            doctor_name = doctor.user.full_name if doctor and doctor.user else "Не назначен"

            return {
                "success": True,
                "visit_id": visit.id,
                "status": visit.status,
                "patient_name": patient.short_name() if patient else "Неизвестный пациент",
                "doctor_name": doctor_name,
                "visit_date": visit.visit_date.isoformat(),
                "visit_time": visit.visit_time,
                "department": visit.department,
                "discount_mode": visit.discount_mode,
                "services": services_info,
                "total_amount": total_amount,
                "currency": "UZS",
                "confirmation_expires_at": (
                    visit.confirmation_expires_at.isoformat()
                    if visit.confirmation_expires_at
                    else None
                ),
                "notes": visit.notes,
            }
        except VisitConfirmationDomainError:
            raise
        except Exception as exc:
            raise VisitConfirmationDomainError(
                status_code=500,
                detail=f"Ошибка получения информации о визите: {exc}",
            ) from exc

    def _confirm_visit(
        self,
        *,
        visit,
        confirmed_by: str,
        channel: str,
        confirmation_phone: str | None = None,
        confirmation_telegram_id: str | None = None,
    ) -> dict[str, Any]:
        visit.confirmed_at = datetime.now(UTC)
        visit.confirmed_by = confirmed_by
        visit.status = "confirmed"

        queue_numbers: list[dict[str, Any]] = []
        print_tickets: list[dict[str, Any]] = []
        if visit.visit_date == date.today():
            queue_numbers, print_tickets = self.assign_queue_numbers_on_confirmation(
                visit,
                confirmation_phone=confirmation_phone,
                confirmation_telegram_id=confirmation_telegram_id,
            )
            visit.status = "open"

        self.repository.commit()
        self.repository.refresh(visit)

        patient = self.repository.get_patient(visit.patient_id)
        return {
            "success": True,
            "message": (
                "✅ Визит подтвержден! "
                + (
                    "Номера в очередях присвоены."
                    if queue_numbers
                    else "Номера будут присвоены утром в день визита."
                )
            ),
            "visit_id": visit.id,
            "status": visit.status,
            "patient_name": patient.short_name() if patient else "Неизвестный пациент",
            "visit_date": visit.visit_date.isoformat(),
            "visit_time": visit.visit_time,
            "queue_numbers": queue_numbers,
            "print_tickets": print_tickets,
        }

    def assign_queue_numbers_on_confirmation(
        self,
        visit,
        *,
        confirmation_phone: str | None = None,
        confirmation_telegram_id: str | int | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return self._assign_queue_numbers_on_confirmation(
            visit,
            confirmation_phone=confirmation_phone,
            confirmation_telegram_id=confirmation_telegram_id,
        )

    @staticmethod
    def _normalize_confirmation_phone(phone: str | None) -> str | None:
        if not phone:
            return None
        normalized_phone = normalize_phone_uz(phone)
        return normalized_phone or None

    @staticmethod
    def _normalize_confirmation_telegram_id(
        telegram_id: str | int | None,
    ) -> int | None:
        if telegram_id in (None, ""):
            return None
        try:
            return int(str(telegram_id).strip())
        except (TypeError, ValueError):
            return None

    def _resolve_existing_active_entry(
        self,
        *,
        daily_queue: DailyQueue,
        visit,
        patient,
        confirmation_phone: str | None,
        confirmation_telegram_id: str | int | None,
    ) -> OnlineQueueEntry | None:
        active_entries = self.repository.get_active_queue_entries(
            queue_id=daily_queue.id,
            active_statuses=CANONICAL_ACTIVE_CONFIRMATION_STATUSES,
        )
        if not active_entries:
            return None

        candidate_entries: dict[int, OnlineQueueEntry] = {}

        if visit.patient_id:
            for entry in active_entries:
                if entry.patient_id == visit.patient_id:
                    candidate_entries[entry.id] = entry

        normalized_phone = self._normalize_confirmation_phone(
            confirmation_phone or (patient.phone if patient else None)
        )
        if normalized_phone:
            for entry in active_entries:
                entry_phone = self._normalize_confirmation_phone(entry.phone)
                if entry_phone and entry_phone == normalized_phone:
                    candidate_entries[entry.id] = entry

        normalized_telegram_id = self._normalize_confirmation_telegram_id(
            confirmation_telegram_id
        )
        if normalized_telegram_id is not None:
            for entry in active_entries:
                if entry.telegram_id == normalized_telegram_id:
                    candidate_entries[entry.id] = entry

        if not candidate_entries:
            return None

        if len(candidate_entries) > 1:
            raise VisitConfirmationDomainError(
                status_code=409,
                detail=(
                    "Cannot unambiguously resolve an existing queue entry "
                    "for visit confirmation"
                ),
            )

        existing_entry = next(iter(candidate_entries.values()))

        if existing_entry.patient_id not in (None, visit.patient_id):
            raise VisitConfirmationDomainError(
                status_code=409,
                detail=(
                    "Cannot unambiguously resolve an existing queue entry "
                    "for visit confirmation"
                ),
            )

        if existing_entry.visit_id not in (None, visit.id):
            raise VisitConfirmationDomainError(
                status_code=409,
                detail=(
                    "Cannot unambiguously resolve an existing queue entry "
                    "for visit confirmation"
                ),
            )

        return existing_entry

    @staticmethod
    def _reuse_existing_active_entry(*, existing_entry: OnlineQueueEntry, visit) -> None:
        if existing_entry.patient_id is None:
            existing_entry.patient_id = visit.patient_id
        if existing_entry.visit_id is None:
            existing_entry.visit_id = visit.id

    def _assign_queue_numbers_on_confirmation(
        self,
        visit,
        *,
        confirmation_phone: str | None = None,
        confirmation_telegram_id: str | int | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        visit_services = self.repository.get_visit_services(visit.id)

        unique_queue_tags: set[str] = set()
        for vs in visit_services:
            service = self.repository.get_service(vs.service_id)
            if service and service.queue_tag:
                unique_queue_tags.add(service.queue_tag)

        if not unique_queue_tags:
            department_to_queue = {
                "cardiology": "cardiology_common",
                "dermatology": "dermatology",
                "stomatology": "stomatology",
                "cosmetology": "cosmetology",
                "lab": "lab",
                "ecg": "ecg",
            }
            fallback_tag = department_to_queue.get((visit.department or "").lower())
            if fallback_tag:
                unique_queue_tags.add(fallback_tag)
            else:
                return [], []

        today = date.today()
        queue_numbers: list[dict[str, Any]] = []
        print_tickets: list[dict[str, Any]] = []
        patient = self.repository.get_patient(visit.patient_id)
        telegram_ticket_qr_payload: str | None = None
        telegram_ticket_qr_resolved = False

        for queue_tag in sorted(unique_queue_tags):
            daily_queue: DailyQueue | None = None
            specialist_doctor_id: int | None = None
            if visit.doctor_id:
                visit_doctor = self.repository.get_doctor(visit.doctor_id)
                if visit_doctor:
                    specialist_doctor_id = visit_doctor.id

            if queue_tag == "ecg" and not specialist_doctor_id:
                ecg_resource = self.repository.get_active_user_by_username("ecg_resource")
                if ecg_resource:
                    ecg_doctor = self.repository.get_doctor_by_user_id(ecg_resource.id)
                    if ecg_doctor:
                        specialist_doctor_id = ecg_doctor.id
                    else:
                        logger.warning(
                            "ECG resource user id=%s has no doctor row",
                            ecg_resource.id,
                        )
            elif queue_tag == "lab" and not specialist_doctor_id:
                lab_resource = self.repository.get_active_user_by_username("lab_resource")
                if lab_resource:
                    lab_doctor = self.repository.get_doctor_by_user_id(lab_resource.id)
                    if lab_doctor:
                        specialist_doctor_id = lab_doctor.id
                        logger.info(
                            "For queue_tag=%s using lab resource doctor id=%s",
                            queue_tag,
                            specialist_doctor_id,
                        )
                    else:
                        logger.warning(
                            "Lab resource user id=%s has no doctor row",
                            lab_resource.id,
                        )

            if not specialist_doctor_id:
                daily_queue = self._get_active_daily_queue_by_tag(today, queue_tag)
                if not daily_queue:
                    logger.info(
                        "No doctor profile or active daily queue for "
                        "confirmation visit_id=%s doctor_id=%s queue_tag=%s",
                        visit.id,
                        visit.doctor_id,
                        queue_tag,
                    )
                    continue

            if daily_queue is None:
                daily_queue = self.repository.get_or_create_daily_queue(
                    day=today,
                    specialist_id=specialist_doctor_id,
                    queue_tag=queue_tag,
                )

            existing_entry = self._resolve_existing_active_entry(
                daily_queue=daily_queue,
                visit=visit,
                patient=patient,
                confirmation_phone=confirmation_phone,
                confirmation_telegram_id=confirmation_telegram_id,
            )
            if existing_entry:
                self._reuse_existing_active_entry(
                    existing_entry=existing_entry,
                    visit=visit,
                )
                queue_number = existing_entry.number
                queue_id = existing_entry.queue_id
            else:
                queue_number = queue_service.get_next_queue_number(
                    self.repository.db,
                    daily_queue=daily_queue,
                    queue_tag=queue_tag,
                )

                created_entry = self.queue_facade.allocate_ticket(
                    allocation_mode="create_entry",
                    daily_queue=daily_queue,
                    patient_id=visit.patient_id,
                    visit_id=visit.id,
                    number=queue_number,
                    source="confirmation",
                )
                queue_number = created_entry.number
                queue_id = created_entry.queue_id

            queue_numbers.append(
                {
                    "queue_tag": queue_tag,
                    "number": queue_number,
                    "queue_id": queue_id,
                }
            )

            queue_names = {
                "ecg": "ЭКГ",
                "cardiology_common": "Кардиолог",
                "dermatology": "Дерматолог",
                "stomatology": "Стоматолог",
                "cosmetology": "Косметолог",
                "lab": "Лаборатория",
                "general": "Общая очередь",
            }
            doctor = self.repository.get_doctor(visit.doctor_id) if visit.doctor_id else None
            patient = self.repository.get_patient(visit.patient_id)

            ticket_payload_extra: dict[str, Any] = {}
            if not telegram_ticket_qr_resolved:
                telegram_ticket_qr_payload = self._build_ticket_telegram_qr_payload(visit)
                telegram_ticket_qr_resolved = True
            if telegram_ticket_qr_payload:
                ticket_payload_extra["qr_payload"] = telegram_ticket_qr_payload

            print_tickets.append(
                {
                    "visit_id": visit.id,
                    "queue_tag": queue_tag,
                    "queue_name": queue_names.get(queue_tag, queue_tag),
                    "queue_number": queue_number,
                    "queue_id": queue_id,
                    "patient_id": visit.patient_id,
                    "patient_name": (
                        patient.short_name() if patient else "Неизвестный пациент"
                    ),
                    "doctor_name": (
                        doctor.user.full_name if doctor and doctor.user else "Без врача"
                    ),
                    "doctor_cabinet": (
                        daily_queue.cabinet_number
                        or (doctor.cabinet if doctor else None)
                    ),
                    "department": visit.department,
                    "visit_date": visit.visit_date.isoformat(),
                    "visit_time": visit.visit_time,
                    **ticket_payload_extra,
                }
            )

        return queue_numbers, print_tickets

    def _build_ticket_telegram_qr_payload(self, visit) -> str | None:
        bot_username = self._resolve_telegram_bot_username()
        if not bot_username:
            return None

        expires_at = datetime.now(UTC) + timedelta(
            minutes=TELEGRAM_TICKET_QR_TTL_MINUTES
        )
        token = build_telegram_ticket_start_token(expires_at=expires_at)
        visit.confirmation_token = _hash_telegram_ticket_start_token(token)
        # Store naive UTC for backward compatibility with existing rows that
        # were written before the schema migrated to ``DateTime(timezone=True)``.
        visit.confirmation_expires_at = _as_utc_naive(expires_at)
        return f"https://t.me/{bot_username}?start={token}"

    def _resolve_telegram_bot_username(self) -> str | None:
        candidates: list[Any] = []
        try:
            config = crud_telegram.get_telegram_config(self.repository.db)
            candidates.append(getattr(config, "bot_username", None))
        except Exception as exc:
            logger.warning(
                "Failed to read Telegram config for ticket QR payload error_type=%s",
                type(exc).__name__,
            )

        try:
            clinic_setting = crud_clinic.get_setting_by_key(
                self.repository.db,
                "bot_username",
            )
            candidates.append(getattr(clinic_setting, "value", None))
        except Exception as exc:
            logger.warning(
                "Failed to read clinic Telegram username setting error_type=%s",
                type(exc).__name__,
            )

        for candidate in candidates:
            if not candidate:
                continue
            username = str(candidate).strip().lstrip("@")
            if TELEGRAM_USERNAME_RE.fullmatch(username):
                return username

        return None

    def _get_active_daily_queue_by_tag(
        self, day: date, queue_tag: str
    ) -> DailyQueue | None:
        return (
            self.repository.db.query(DailyQueue)
            .filter(
                DailyQueue.day == day,
                DailyQueue.queue_tag == queue_tag,
                DailyQueue.active.is_(True),
            )
            .order_by(DailyQueue.id.asc())
            .first()
        )
