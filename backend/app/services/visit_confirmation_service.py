"""Service layer for visit confirmation endpoints."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import re
import secrets
import struct
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlsplit

from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.crud import clinic as crud_clinic
from app.crud import telegram_config as crud_telegram
from app.crud.queue_owner_invariant import QueueProfileBindingChanged
from app.crud.queue_owner_policy import (
    eligible_real_doctor,
    owner_configuration_error,
)
from app.crud.queue_resource_routing import resolve_tag_resource, tag_routes_to_resource
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.service import Service
from app.models.telegram_config import TelegramUser
from app.models.visit import Visit, VisitService
from app.repositories.visit_confirmation_repository import VisitConfirmationRepository
from app.services.all_free_approval import (
    ALL_FREE_DECISION_REQUIRED,
    all_free_decision_required_clause,
)
from app.services.confirmation_security import ConfirmationSecurityService
from app.services.context_facades.queue_facade import (
    QueueContextFacade,
    QueueDomainServiceContractAdapter,
)
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    lock_group_without_pending,
)
from app.services.patient_subject_lock import (
    PatientSubjectLockError,
    lock_patient_subject,
    require_patient_subject_visibility,
)
from app.services.queue_claim_service import (
    QueueClaimConflictError,
    lock_and_resolve_active_tag_claim,
)
from app.services.queue_service import queue_service
from app.services.telegram_token_store import resolve_patient_bot_token

logger = logging.getLogger(__name__)

# SSOT: день КЛИНИКИ — канонический хелпер живёт в crud.clinic рядом с
# get_queue_settings (нейтральный слой, доступный всем контекстам).
from app.crud.clinic import clinic_today as _clinic_today  # noqa: E402

CONFIRMATION_PROCESSING_STATUS = "confirmation_processing"


def _telegram_review_base_url() -> str:
    """Validate only the origin used to deliver a new review capability."""
    value = settings.FRONTEND_URL
    try:
        if not isinstance(value, str) or not value or any(
            ord(character) <= 32 or ord(character) == 127 or character == "\\"
            for character in value
        ):
            raise ValueError
        parsed = urlsplit(value)
        host = parsed.hostname
        if (not host or "%" in host or "?" in value or "#" in value
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.port == 0):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
            mapped = getattr(address, "ipv4_mapped", None)
            is_loopback = (address.is_loopback or address.is_unspecified
                           or bool(mapped and (mapped.is_loopback or mapped.is_unspecified)))
        except ValueError:
            domain = host.encode("idna").decode("ascii")
            if (len(domain) > 253 or not all(
                re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                for label in domain.split(".")
            ) or re.fullmatch(r"[0-9.]+", domain)
                or re.fullmatch(r"(?:[0-9]+|0[xX][0-9a-fA-F]+)", domain.split(".")[-1])):
                raise ValueError
            is_loopback = domain.lower() == "localhost" or domain.lower().endswith(".localhost")
        local_allowed = (
            settings.ALLOW_INSECURE_LOCAL_TELEGRAM_REVIEW
            and settings.ENV.strip().lower() in {"dev", "development", "test", "testing"}
            and host.lower() in {"localhost", "127.0.0.1", "::1"}
        )
        if is_loopback and not local_allowed:
            raise ValueError
        if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback and local_allowed):
            raise ValueError
        return value.rstrip("/")
    except (AttributeError, UnicodeError, ValueError):
        raise VisitConfirmationDomainError(status_code=503, detail="Просмотр приглашения недоступен") from None

TELEGRAM_TICKET_QR_PREFIX = "tq"
TELEGRAM_TICKET_QR_HASH_PREFIX = "ticket_qr:"
TELEGRAM_TICKET_QR_SEPARATOR = "_"
TELEGRAM_TICKET_QR_TTL_MINUTES = 15
TELEGRAM_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")
TELEGRAM_VISIT_ACTION_PREFIX = "tv"


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


def build_telegram_visit_action_token(
    *, visit_id: int, confirmation_token: str, link_id: int,
    chat_id: int, patient_id: int, link_epoch: int, visit_context_epoch: int,
    purpose: str = "action",
) -> str:
    """Derive a compact chat-bound capability without exposing the PWA token.

    The 32-byte packed token has a 128-bit MAC and fits Telegram's 64-byte
    callback_data limit including the ``confirm_visit:`` action prefix.
    Changing the underlying visit token or link generation invalidates it.
    """
    if (not confirmation_token or not settings.SECRET_KEY or purpose not in {"view", "action"}
        or isinstance(chat_id, bool) or not isinstance(chat_id, int) or not 0 < chat_id < 2**63
        or isinstance(visit_context_epoch, bool) or not isinstance(visit_context_epoch, int)
        or not 0 <= visit_context_epoch < 2**63):
        raise ValueError("Visit invitation is unavailable")
    try:
        packed = struct.pack(">IIQ", visit_id, link_id, link_epoch)
    except (struct.error, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Visit invitation is unavailable") from exc
    binding = json.dumps(
        [chat_id, patient_id, confirmation_token, visit_context_epoch], separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        b"telegram-visit-" + purpose.encode("ascii") + b"-v1\0" + packed + b"\0" + binding,
        hashlib.sha256,
    ).digest()[:16]
    # Derive a per-capability mask from its authentication tag so identifiers
    # are not readable from callback_data. The tag is verified after lookup.
    mask = hmac.new(settings.SECRET_KEY.encode("utf-8"),
                    b"telegram-visit-mask-v1\0" + digest, hashlib.sha256).digest()[:16]
    encrypted = bytes(a ^ b for a, b in zip(packed, mask, strict=True))
    encoded = base64.urlsafe_b64encode(encrypted + digest).rstrip(b"=").decode("ascii")
    return ("tv" if purpose == "view" else "ta") + encoded


def _parse_telegram_visit_action_token(token: str) -> tuple[int, int, int] | None:
    if not isinstance(token, str) or not re.fullmatch(r"t[va][A-Za-z0-9_-]{43}", token):
        return None
    try:
        raw = base64.b64decode(token[2:] + "=", altchars=b"-_", validate=True)
        if len(raw) != 32:
            return None
        mask = hmac.new(settings.SECRET_KEY.encode("utf-8"),
                        b"telegram-visit-mask-v1\0" + raw[16:], hashlib.sha256).digest()[:16]
        packed = bytes(a ^ b for a, b in zip(raw[:16], mask, strict=True))
        visit_id, link_id, epoch = struct.unpack(">IIQ", packed)
        if not visit_id or not link_id or epoch > 2**63 - 1:
            return None
        return visit_id, link_id, epoch
    except (TypeError, ValueError, struct.error):
        return None


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


def build_telegram_ticket_start_token(
    *, expires_at: datetime, nonce: str | None = None
) -> str:
    """Build a compact signed Telegram /start payload without patient data."""
    exp = int(_as_utc_naive(expires_at).replace(tzinfo=UTC).timestamp())
    token_nonce = nonce or _base36_encode(secrets.randbits(48))
    body = (
        f"{TELEGRAM_TICKET_QR_PREFIX}{TELEGRAM_TICKET_QR_SEPARATOR}"
        f"{_base36_encode(exp)}{TELEGRAM_TICKET_QR_SEPARATOR}{token_nonce}"
    )
    return f"{body}{TELEGRAM_TICKET_QR_SEPARATOR}" f"{_ticket_qr_signature(body)}"


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
    try:
        # The webhook links the chat before committing this transaction. Keep
        # the patient and visit locked until then so ownership cannot change
        # between consuming the ticket and creating the link.
        visit = VisitConfirmationService(db)._lock_confirmation_visit(token_hash)
    except VisitConfirmationDomainError as exc:
        if exc.status_code == 404:
            return None
        raise

    if (
        visit.confirmation_expires_at
        and _as_aware_utc(visit.confirmation_expires_at) < now
    ):
        return None

    updated = (
        db.query(Visit)
        .filter(Visit.id == visit.id, Visit.patient_id == visit.patient_id,
                Visit.confirmation_token == token_hash)
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

    def _require_full_subject_visibility(self) -> None:
        try:
            require_patient_subject_visibility(self.repository.db)
        except PatientSubjectLockError as exc:
            raise VisitConfirmationDomainError(status_code=exc.status_code, detail=exc.detail) from None

    def _lock_confirmation_patient(self, token: str, *, expected_visit_id: int | None = None) -> int:
        """Use token lookup only as a hint; lock patient before visit mutation."""
        db = self.repository.db
        self._require_full_subject_visibility()
        query = db.query(Visit.id, Visit.patient_id).filter(Visit.confirmation_token == token)
        if expected_visit_id is not None:
            query = query.filter(Visit.id == expected_visit_id)
        hints = query.limit(2).all()
        if len(hints) != 1 or hints[0].patient_id is None:
            raise VisitConfirmationDomainError(status_code=404, detail="Приглашение недоступно")
        patient_id = hints[0].patient_id
        try:
            active = lock_patient_subject(db, patient_id)
        except PatientSubjectLockError as exc:
            raise VisitConfirmationDomainError(status_code=exc.status_code, detail=exc.detail) from None
        if not active:
            raise VisitConfirmationDomainError(status_code=404, detail="Приглашение недоступно")
        return patient_id

    def _lock_confirmation_group(self, visit_id: int) -> None:
        try:
            lock_group_without_pending(self.repository.db, visit_id)
        except FinancialFenceError:
            raise VisitConfirmationDomainError(status_code=409, detail="Визит сейчас недоступен") from None
        except HTTPException as exc:
            raise VisitConfirmationDomainError(status_code=exc.status_code, detail="Визит сейчас недоступен") from None
        except DBAPIError as exc:
            code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
            if code in {"40P01", "55P03"}:
                raise VisitConfirmationDomainError(status_code=409, detail="Визит сейчас недоступен") from None
            raise

    def _lock_confirmation_visit(self, token: str, *, expected_visit_id: int | None = None,
                                 require_financial_clear: bool = False) -> Visit:
        patient_id = self._lock_confirmation_patient(token, expected_visit_id=expected_visit_id)
        if require_financial_clear:
            # The earlier token lookup was only a hint. The group helper locks
            # every Visit before Encounter; the token is rechecked afterwards.
            visit_hint = (self.repository.db.query(Visit.id)
                          .filter(Visit.confirmation_token == token).first())
            if visit_hint is None or (expected_visit_id is not None and visit_hint.id != expected_visit_id):
                raise VisitConfirmationDomainError(status_code=404, detail="Приглашение недоступно")
            self._lock_confirmation_group(visit_hint.id)
        query = self.repository.db.query(Visit).filter(Visit.confirmation_token == token)
        if expected_visit_id is not None:
            query = query.filter(Visit.id == expected_visit_id)
        visit = query.with_for_update().populate_existing().first()
        if visit is None or visit.patient_id != patient_id:
            raise VisitConfirmationDomainError(status_code=404, detail="Приглашение недоступно")
        return visit

    def _claim_pending_visit_for_confirmation(
        self, token: str, *, expected_visit_id: int | None = None
    ) -> Visit | None:
        # PR-1 (Codex round 16, P2): the claim transition itself must be
        # lease-coordinated. The patient-confirm flow used to grab the row
        # (pending_confirmation → confirmation_processing) FIRST and only
        # then run the round-15 pre-lock lease wait in
        # VisitLifecycleService.confirm_visit — that wait polled the lease
        # while the worker's finalize UPDATE was blocked on the very row
        # lock this claim holds, burning the whole budget and 409-ing the
        # patient. Now: (1) wait for a live lease BEFORE the claim (no row
        # lock held), and (2) bind the claim UPDATE ITSELF to the
        # no-live-lease predicate, so a claim landing between the wait and
        # the update makes THIS claim lose atomically.
        from sqlalchemy import or_ as _or

        from app.tasks.lease import (
            LEASE_TTL,
            REMINDER_IN_PROGRESS_DETAIL,
            wait_for_reminder_lease_clear,
        )

        approval_required = all_free_decision_required_clause()
        # The lease pre-read uses a bare COLUMN select (like
        # lease.wait_for_reminder_lease_clear itself): a column select
        # never returns the cached identity-map instance, so it sees the
        # freshest committed lease even when this session already holds
        # the visit object (with possibly pending local changes).
        pending_query = (
            self.repository.db.query(Visit.id)
            .filter(
                Visit.confirmation_token == token,
                Visit.status == "pending_confirmation",
                ~approval_required,
            )
        )
        if expected_visit_id is not None:
            pending_query = pending_query.filter(Visit.id == expected_visit_id)
        pending = pending_query.first()
        if pending is not None and hasattr(Visit, "reminder_claimed_at"):
            claimed_at = (
                self.repository.db.query(Visit.reminder_claimed_at)
                .filter(Visit.id == pending.id)
                .scalar()
            )
            if claimed_at is not None:
                from datetime import UTC, datetime

                if claimed_at.tzinfo is None:
                    claimed_at = claimed_at.replace(tzinfo=UTC)
                if datetime.now(UTC) - claimed_at < LEASE_TTL:
                    if not wait_for_reminder_lease_clear(
                        self.repository.db, pending.id
                    ):
                        raise VisitConfirmationDomainError(
                            status_code=409,
                            detail=REMINDER_IN_PROGRESS_DETAIL,
                        )

        patient_id = self._lock_confirmation_patient(token, expected_visit_id=expected_visit_id)
        group_hint = (self.repository.db.query(Visit.id)
                      .filter(Visit.confirmation_token == token).first())
        if group_hint is None or (expected_visit_id is not None and group_hint.id != expected_visit_id):
            raise VisitConfirmationDomainError(status_code=404, detail="Приглашение недоступно")
        self._lock_confirmation_group(group_hint.id)
        lease_free = None
        if hasattr(Visit, "reminder_claimed_at"):
            from datetime import UTC, datetime

            from app.tasks.lease import LEASE_TTL

            lease_free = _or(
                Visit.reminder_claimed_at.is_(None),
                Visit.reminder_claimed_at < datetime.now(UTC) - LEASE_TTL,
            )
        claim_filters = [
            Visit.confirmation_token == token,
            Visit.status == "pending_confirmation",
            ~approval_required,
        ]
        if expected_visit_id is not None:
            claim_filters.append(Visit.id == expected_visit_id)
        if lease_free is not None:
            claim_filters.append(lease_free)
        updated = (
            self.repository.db.query(Visit)
            .filter(*claim_filters)
            .update(
                {Visit.status: CONFIRMATION_PROCESSING_STATUS},
                synchronize_session=False,
            )
        )
        if updated == 0:
            # Distinguish the loser's cause: a live reminder claim (409)
            # vs the token raced away / already processed (None).
            # The cause check reads bare COLUMNS so it never consults
            # the identity map's possibly-stale copy.
            raced_query = (
                self.repository.db.query(
                    Visit.id,
                    Visit.status,
                    Visit.reminder_claimed_at,
                    approval_required.label("all_free_decision_required"),
                )
                .filter(Visit.confirmation_token == token)
            )
            if expected_visit_id is not None:
                raced_query = raced_query.filter(Visit.id == expected_visit_id)
            raced_row = raced_query.first()
            if (
                raced_row is not None
                and raced_row.status == "pending_confirmation"
                and raced_row.all_free_decision_required
            ):
                raise VisitConfirmationDomainError(409, ALL_FREE_DECISION_REQUIRED)
            if (
                raced_row is not None
                and raced_row.status == "pending_confirmation"
                and raced_row.reminder_claimed_at is not None
            ):
                from datetime import UTC, datetime

                from app.tasks.lease import LEASE_TTL

                raced_claim = raced_row.reminder_claimed_at
                if raced_claim.tzinfo is None:
                    raced_claim = raced_claim.replace(tzinfo=UTC)
                if datetime.now(UTC) - raced_claim < LEASE_TTL:
                    raise VisitConfirmationDomainError(
                        status_code=409,
                        detail=REMINDER_IN_PROGRESS_DETAIL,
                    )
            return None
        if updated != 1:
            raise VisitConfirmationDomainError(
                status_code=409,
                detail="Ambiguous confirmation token",
            )

        self.repository.db.flush()
        claimed_query = (
            self.repository.db.query(Visit)
            .filter(
                Visit.confirmation_token == token,
                Visit.status == CONFIRMATION_PROCESSING_STATUS,
            )
        )
        if expected_visit_id is not None:
            claimed_query = claimed_query.filter(Visit.id == expected_visit_id)
        visit = claimed_query.populate_existing().first()
        if visit is None or visit.patient_id != patient_id:
            raise VisitConfirmationDomainError(status_code=404, detail="Приглашение недоступно")
        return visit

    def _resolve_telegram_visit_action_token(self, token: str, *, purpose: str = "action") -> tuple[int, int, int, str]:
        """Resolve a signed capability; the underlying PWA token stays local."""
        self._require_full_subject_visibility()
        parsed = _parse_telegram_visit_action_token(token)
        if parsed is None:
            raise VisitConfirmationDomainError(status_code=404, detail="Приглашение недействительно")
        visit_id, link_id, epoch = parsed
        row = (
            self.repository.db.query(
                Visit.confirmation_token, Visit.patient_id,
                TelegramUser.id, TelegramUser.chat_id, TelegramUser.patient_id,
                TelegramUser.patient_link_epoch, Visit.confirmation_context_epoch,
            )
            .select_from(Visit)
            .join(TelegramUser, TelegramUser.id == link_id)
            .filter(Visit.id == visit_id)
            .first()
        )
        if row is None or not row[0] or row[1] != row[4] or row[5] != epoch:
            raise VisitConfirmationDomainError(status_code=404, detail="Приглашение недействительно")
        expected = build_telegram_visit_action_token(
            visit_id=visit_id, confirmation_token=row[0], link_id=link_id,
            chat_id=row[3], patient_id=row[1], link_epoch=epoch,
            visit_context_epoch=row[6], purpose=purpose,
        )
        if not hmac.compare_digest(token, expected):
            raise VisitConfirmationDomainError(status_code=404, detail="Приглашение недействительно")
        return visit_id, link_id, epoch, row[0]

    def _require_linked_telegram_actor(
        self, visit: Visit, telegram_user_id: str | None, *,
        capability: str, link_id: int, link_epoch: int, purpose: str = "action",
    ) -> None:
        """Bind a trusted private-chat actor to the patient on the locked visit.

        The caller must only supply an actor from an authenticated Telegram
        update after verifying that the sender and private chat IDs match.
        The link lock makes revocation and visit action serialize.
        """
        actor = str(telegram_user_id or "")
        if not re.fullmatch(r"[1-9][0-9]{0,18}", actor) or int(actor) > 2**63 - 1:
            raise VisitConfirmationDomainError(
                status_code=403, detail="Действие недоступно для этого чата"
            )
        link = (
            self.repository.db.query(TelegramUser)
            .filter(
                TelegramUser.chat_id == int(actor),
                TelegramUser.id == link_id,
                TelegramUser.patient_id == visit.patient_id,
                TelegramUser.patient_link_epoch == link_epoch,
                TelegramUser.active.is_(True),
                TelegramUser.blocked.is_(False),
                TelegramUser.notifications_enabled.is_(True),
                TelegramUser.appointment_reminders.is_(True),
            )
            .with_for_update()
            .populate_existing()
            .first()
        )
        if link is None:
            raise VisitConfirmationDomainError(
                status_code=403, detail="Действие недоступно для этого чата"
            )
        expected = build_telegram_visit_action_token(
            visit_id=visit.id, confirmation_token=visit.confirmation_token,
            link_id=link.id, chat_id=link.chat_id, patient_id=visit.patient_id,
            link_epoch=link.patient_link_epoch,
            visit_context_epoch=visit.confirmation_context_epoch, purpose=purpose,
        )
        if not hmac.compare_digest(capability, expected):
            raise VisitConfirmationDomainError(status_code=403, detail="Действие недоступно для этого чата")

    def preview_by_telegram(self, *, token: str, telegram_user_id: str) -> dict[str, str]:
        """Validate under locks; caller releases transaction before provider delivery."""
        visit_id, link_id, link_epoch, raw_token = self._resolve_telegram_visit_action_token(token, purpose="view")
        visit = self._lock_confirmation_visit(raw_token, expected_visit_id=visit_id, require_financial_clear=True)
        if visit is None or visit.status != "pending_confirmation":
            raise VisitConfirmationDomainError(status_code=404, detail="Приглашение недоступно")
        self._require_valid_telegram_invitation(visit, raw_token)
        self._require_linked_telegram_actor(visit, telegram_user_id, capability=token,
                                            link_id=link_id, link_epoch=link_epoch, purpose="view")
        action_token = build_telegram_visit_action_token(
            visit_id=visit.id, confirmation_token=raw_token, link_id=link_id,
            chat_id=int(telegram_user_id), patient_id=visit.patient_id, link_epoch=link_epoch,
            visit_context_epoch=visit.confirmation_context_epoch,
        )
        # The recipient can change after locks are released and before Telegram
        # accepts the message. Keep the transport neutral and read details only
        # through the current, revocable confirmation capability.
        view_url = (f"{_telegram_review_base_url()}/confirm-visit"
                    f"#token={quote(token, safe='')}&review=telegram")
        return {"text": "У вас новое уведомление.", "view_url": view_url,
                "action_token": action_token}

    @staticmethod
    def _require_valid_telegram_invitation(visit: Visit, token: str) -> None:
        """Recheck mutable token properties under the locked visit row."""
        if visit.confirmation_token != token or visit.confirmation_channel not in (
            "telegram", "auto", None, ""
        ):
            raise VisitConfirmationDomainError(
                status_code=400, detail="Приглашение недействительно"
            )
        expires_at = visit.confirmation_expires_at
        if expires_at is None or _as_aware_utc(expires_at) <= datetime.now(UTC):
            raise VisitConfirmationDomainError(
                status_code=400, detail="Срок действия приглашения истек"
            )
        # A future date without time is unambiguous; today without time is
        # rejected because the start may already have passed.
        from app.tasks.worker import _appointment_start_utc, _clinic_timezone

        if visit.visit_date is None:
            raise VisitConfirmationDomainError(status_code=400, detail="Время визита недоступно")
        if not visit.visit_time:
            if visit.visit_date <= datetime.now(UTC).astimezone(_clinic_timezone()).date():
                raise VisitConfirmationDomainError(status_code=400, detail="Время визита недоступно")
            return
        if not re.fullmatch(r"\d{2}:\d{2}", visit.visit_time):
            raise VisitConfirmationDomainError(status_code=400, detail="Время визита недоступно")
        start = _appointment_start_utc(visit)
        if start is None or start <= datetime.now(UTC):
            raise VisitConfirmationDomainError(status_code=400, detail="Время визита недоступно")

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
            capability = token
            visit_id, link_id, link_epoch, token = self._resolve_telegram_visit_action_token(capability)
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

            visit = self._claim_pending_visit_for_confirmation(
                token, expected_visit_id=visit_id
            )
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

            self._require_valid_telegram_invitation(visit, token)
            self._require_linked_telegram_actor(
                visit, telegram_user_id, capability=capability,
                link_id=link_id, link_epoch=link_epoch,
            )

            result = self._confirm_visit(
                visit=visit,
                confirmed_by=f"telegram_{telegram_user_id or 'unknown'}",
                channel="telegram",
                confirmation_telegram_id=telegram_user_id,
            )

            self.security_service.record_confirmation_attempt(
                visit_id=result["visit_id"],
                success=True,
                channel="telegram",
            )
            result.pop("patient_name", None)
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
                    error_reason="System error",
                )
            except Exception:
                pass
            raise VisitConfirmationDomainError(
                status_code=500,
                detail="Не удалось подтвердить визит",
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
            self._require_full_subject_visibility()
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

            if not visit.confirmation_expires_at or _as_aware_utc(
                visit.confirmation_expires_at
            ) <= datetime.now(UTC):
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
                visit_id=result["visit_id"], success=True, channel="pwa"
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

    def cancel_by_telegram(
        self,
        *,
        token: str,
        telegram_user_id: str | None = None,
        source_ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Cancel only for the verified actor from a trusted Telegram update."""
        try:
            capability = token
            visit_id, link_id, link_epoch, token = self._resolve_telegram_visit_action_token(capability)
            security_check = self.security_service.validate_confirmation_request(
                token=token, source_ip=source_ip, user_agent=user_agent,
                channel="telegram",
            )
            if not security_check.allowed:
                if security_check.reason == "Недействительный токен подтверждения":
                    raise VisitConfirmationDomainError(
                        status_code=404, detail="Приглашение недействительно или уже использовано"
                    )
                raise VisitConfirmationDomainError(
                    status_code=429 if security_check.retry_after else 400,
                    detail="Приглашение недействительно или недоступно",
                    headers=(
                        {"Retry-After": str(security_check.retry_after)}
                        if security_check.retry_after else None
                    ),
                )

            # Wait without holding the row lock: reminder finalization needs
            # that same lock. The lease is rechecked after locking below.
            from app.tasks.lease import LEASE_TTL, wait_for_reminder_lease_clear

            candidate = (
                self.repository.db.query(Visit.id, Visit.reminder_claimed_at)
                .filter(Visit.id == visit_id, Visit.confirmation_token == token)
                .first()
            )
            if candidate is not None and candidate.reminder_claimed_at is not None:
                if datetime.now(UTC) - _as_aware_utc(candidate.reminder_claimed_at) < LEASE_TTL:
                    if not wait_for_reminder_lease_clear(self.repository.db, candidate.id):
                        raise VisitConfirmationDomainError(
                            status_code=409, detail="Визит сейчас обрабатывается"
                        )
            visit = self._lock_confirmation_visit(token, expected_visit_id=visit_id, require_financial_clear=True)
            if visit is None:
                raise VisitConfirmationDomainError(
                    status_code=404,
                    detail="Визит по токену не найден — возможно, ссылка уже использована",
                )
            if visit.status != "pending_confirmation":
                raise VisitConfirmationDomainError(
                    status_code=409,
                    detail="Визит уже обработан — для отмены свяжитесь с клиникой",
                )
            claimed_at = getattr(visit, "reminder_claimed_at", None)
            if claimed_at is not None:
                if datetime.now(UTC) - _as_aware_utc(claimed_at) < LEASE_TTL:
                    raise VisitConfirmationDomainError(
                        status_code=409,
                        detail=(
                            "Визит сейчас обрабатывается — повторите попытку "
                            "через минуту или свяжитесь с клиникой"
                        ),
                    )

            self._require_valid_telegram_invitation(visit, token)
            self._require_linked_telegram_actor(
                visit, telegram_user_id, capability=capability,
                link_id=link_id, link_epoch=link_epoch,
            )

            class _CancelActor:
                id = "patient_telegram"

            from app.services.visit_lifecycle_service import VisitLifecycleService

            lifecycle = VisitLifecycleService(self.repository.db)
            lifecycle.cancel_visit(
                visit_id=visit.id,
                current_user=_CancelActor(),
                commit=False,
            )
            visit.confirmation_token = None
            visit.confirmation_expires_at = None
            self.repository.db.flush()
            result = {
                "success": True,
                "message": "❌ Визит отменен",
                "visit_id": visit.id,
                "status": visit.status,
            }
            self.repository.commit()
            logger.info("telegram visit cancel visit_id=%s", result["visit_id"])
            return result
        except VisitConfirmationDomainError:
            self.repository.rollback()
            raise
        except Exception as exc:
            self.repository.rollback()
            raise VisitConfirmationDomainError(
                status_code=500,
                detail="Не удалось отменить визит",
            ) from exc

    def get_visit_info(self, token: str) -> dict[str, Any]:
        try:
            telegram_context = None
            raw_token = token
            if re.fullmatch(r"tv[A-Za-z0-9_-]{43}", token):
                visit_id, link_id, link_epoch, raw_token = self._resolve_telegram_visit_action_token(
                    token, purpose="view"
                )
                telegram_context = (visit_id, link_id, link_epoch)
            visit = self._lock_confirmation_visit(
                raw_token,
                expected_visit_id=telegram_context[0] if telegram_context else None,
                require_financial_clear=True,
            )
            if not visit:
                raise VisitConfirmationDomainError(
                    status_code=404,
                    detail="Визит не найден",
                )

            if telegram_context:
                _, link_id, link_epoch = telegram_context
                # The signed capability proves possession, while the current
                # locked link proves it has not been revoked or rebound.
                link = (self.repository.db.query(TelegramUser)
                        .filter(TelegramUser.id == link_id).first())
                if link is None:
                    raise VisitConfirmationDomainError(status_code=404, detail="Приглашение недоступно")
                self._require_valid_telegram_invitation(visit, raw_token)
                self._require_linked_telegram_actor(
                    visit, str(link.chat_id), capability=token, link_id=link_id,
                    link_epoch=link_epoch, purpose="view",
                )

            if not visit.confirmation_expires_at or _as_aware_utc(
                visit.confirmation_expires_at
            ) <= datetime.now(UTC):
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
            from app.services.payment_invariant_service import PaymentInvariantService

            try:
                quote = PaymentInvariantService(self.repository.db).compute_visit_quote(visit)
            except HTTPException as exc:
                raise VisitConfirmationDomainError(status_code=exc.status_code,
                                                   detail="Стоимость визита требует проверки") from None
            visit_services = self.repository.get_visit_services(visit.id)
            if {service.id for service in visit_services} != set(quote.line_totals):
                raise VisitConfirmationDomainError(status_code=409, detail="Стоимость визита требует проверки")

            services_info = []
            for vs in visit_services:
                services_info.append(
                    {
                        "name": vs.name,
                        "code": vs.code,
                        "quantity": vs.qty,
                        "price": float(vs.price) if vs.price else 0.0,
                        "total": float(quote.line_totals[vs.id]),
                    }
                )

            doctor = (
                self.repository.get_doctor(visit.doctor_id) if visit.doctor_id else None
            )
            doctor_name = (
                doctor.user.full_name if doctor and doctor.user else "Не назначен"
            )

            return {
                "success": True,
                "visit_id": visit.id,
                "status": visit.status,
                "patient_name": (
                    patient.short_name() if patient else "Неизвестный пациент"
                ),
                "doctor_name": doctor_name,
                "visit_date": visit.visit_date.isoformat(),
                "visit_time": visit.visit_time,
                "department": visit.department,
                "discount_mode": visit.discount_mode,
                "services": services_info,
                "total_amount": float(quote.total),
                "currency": quote.currency,
                "confirmation_expires_at": (
                    visit.confirmation_expires_at.isoformat()
                    if visit.confirmation_expires_at
                    else None
                ),
                # PR 3407 delta review P2: the confirmation card is a
                # PUBLIC, bearer-token-addressed projection, so it is built
                # patient-safe at the capability level — ``notes`` (clinical
                # text: diagnosis markers, cancel reasons, force-reopen audit
                # lines) must never be readable through any token-addressed
                # route (both the legacy GET and the POST share this card).
            }
        except VisitConfirmationDomainError as exc:
            if exc.status_code == 404:
                raise VisitConfirmationDomainError(status_code=404, detail="Визит не найден") from None
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
        # The patient may view an unknown currency, but must not confirm an
        # ambiguous financial amount. Group and subject locks are held here.
        from app.services.payment_invariant_service import PaymentInvariantService

        try:
            quote = PaymentInvariantService(self.repository.db).compute_visit_quote(visit)
        except HTTPException as exc:
            raise VisitConfirmationDomainError(status_code=exc.status_code, detail=exc.detail) from exc
        if quote.currency is None:
            raise VisitConfirmationDomainError(
                status_code=409, detail="Валюта услуг требует проверки администратором"
            )

        # Issue #06 Phase 3 (Gate D): delegate to VisitLifecycleService
        # with commit=False to preserve the original transaction boundary.
        #
        # Original semantics (lines 478-491 before migration):
        #   1. visit.confirmed_at = now()
        #   2. visit.confirmed_by = confirmed_by
        #   3. visit.status = "confirmed"
        #   4. if same-day: assign_queue_numbers_on_confirmation(...)
        #   5. visit.status = "open"
        #   6. self.repository.commit()  ← ONE commit for the whole flow
        #
        # Migration: use commit=False for confirm_visit() and
        # activate_confirmed_visit(), then commit ONCE at the end.
        # This preserves the atomicity of "confirm + queue + activate".
        from app.services.visit_lifecycle_service import VisitLifecycleService

        # Create a lightweight user-like object for audit logging.
        class _ConfirmationActor:
            def __init__(self, confirmed_by: str) -> None:
                self.id = confirmed_by

        actor = _ConfirmationActor(confirmed_by)
        lifecycle = VisitLifecycleService(self.repository.db)

        # Step 1: confirm_visit(commit=False) — pending_confirmation → confirmed
        visit = lifecycle.confirm_visit(
            visit_id=visit.id,
            current_user=actor,
            confirmed_by=confirmed_by,
            commit=False,
        )

        queue_numbers: list[dict[str, Any]] = []
        print_tickets: list[dict[str, Any]] = []
        if visit.visit_date == _clinic_today(self.repository.db):
            queue_numbers, print_tickets = self.assign_queue_numbers_on_confirmation(
                visit,
                confirmation_phone=confirmation_phone,
                confirmation_telegram_id=confirmation_telegram_id,
            )
            # Step 2: activate_confirmed_visit(commit=False) — confirmed → open
            visit = lifecycle.activate_confirmed_visit(
                visit_id=visit.id,
                current_user=actor,
                commit=False,
            )

        # Freeze the entire response while Patient/Visit are still locked.
        # After commit a transfer could otherwise make a refreshed Visit or
        # Patient belong to somebody other than the bearer that was checked.
        self.repository.db.flush()
        self.repository.refresh(visit)
        patient = self.repository.get_patient(visit.patient_id)
        result = {
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
        # Step 3: caller commits ONCE (preserves original atomicity).
        self.repository.commit()
        return result

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
    def _assert_existing_claim_owner(
        *,
        daily_queue: DailyQueue,
        specialist_id: int | None,
        queue_resource_id: int | None,
        expected_daily_queue_id: int | None,
        queue_tag: str,
    ) -> None:
        if expected_daily_queue_id is not None:
            if daily_queue.id == expected_daily_queue_id:
                return
            raise VisitConfirmationDomainError(
                status_code=409,
                detail=(
                    "Existing queue claim belongs to a different owner "
                    f"for queue_tag={queue_tag}"
                ),
            )

        doctor_owner_matches = (
            specialist_id is not None
            and daily_queue.specialist_id == specialist_id
            and daily_queue.queue_resource_id is None
        )
        resource_owner_matches = (
            queue_resource_id is not None
            and daily_queue.queue_resource_id == queue_resource_id
            and daily_queue.specialist_id is None
        )
        if doctor_owner_matches or resource_owner_matches:
            return
        raise VisitConfirmationDomainError(
            status_code=409,
            detail=(
                "Existing queue claim belongs to a different owner "
                f"for queue_tag={queue_tag}"
            ),
        )

    @staticmethod
    def _reuse_existing_active_entry(
        *, existing_entry: OnlineQueueEntry, visit
    ) -> None:
        if existing_entry.visit_id not in (None, visit.id):
            raise VisitConfirmationDomainError(
                status_code=409,
                detail=(
                    "Cannot unambiguously resolve an existing queue entry "
                    "for visit confirmation"
                ),
            )
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

        today = _clinic_today(self.repository.db)
        queue_numbers: list[dict[str, Any]] = []
        print_tickets: list[dict[str, Any]] = []
        unowned_queue_tags: list[str] = []
        patient = self.repository.get_patient(visit.patient_id)
        telegram_ticket_qr_payload: str | None = None
        telegram_ticket_qr_resolved = False

        for queue_tag in sorted(unique_queue_tags):
            # Lock and resolve the patient claim before reading any routing
            # owner. Every writer uses this exact (day, tag) transaction lock,
            # and sorted acquisition keeps multi-tag confirmations ordered.
            try:
                existing_claim = lock_and_resolve_active_tag_claim(
                    self.repository.db,
                    day=today,
                    queue_tag=queue_tag,
                    patient_id=visit.patient_id,
                    phone=(
                        confirmation_phone
                        or (patient.phone if patient is not None else None)
                    ),
                    telegram_id=confirmation_telegram_id,
                    # RQ-25.a.1 (S-22): the legacy-phone bridge is
                    # name-narrowed so family members sharing one phone
                    # each keep their own claim.
                    patient_name=(
                        patient.short_name() if patient is not None else None
                    ),
                )
            except QueueClaimConflictError as exc:
                raise VisitConfirmationDomainError(
                    status_code=409,
                    detail=(
                        "Cannot unambiguously resolve an existing queue entry "
                        "for visit confirmation"
                    ),
                ) from exc
            except QueueProfileBindingChanged as exc:
                raise VisitConfirmationDomainError(
                    status_code=409,
                    detail=(
                        "Queue direction changed during visit confirmation. "
                        "Refresh and retry the confirmation."
                    ),
                ) from exc

            daily_queue: DailyQueue | None = None
            specialist_doctor_id: int | None = None
            registry_surface = tag_routes_to_resource(
                self.repository.db, queue_tag, today
            )
            registry_resource = resolve_tag_resource(self.repository.db, queue_tag)
            registry_tag = registry_surface is not None or registry_resource is not None

            if visit.doctor_id and not registry_tag:
                visit_doctor = self.repository.get_doctor(visit.doctor_id)
                if visit_doctor:
                    specialist_doctor_id = visit_doctor.id

            # QD-2C runtime switch: тег со строкой в queue_resources
            # (сиды 0059 — lab/ecg) маршрутизируется на РЕСУРСНОЙ оси:
            # синтетик не резолвится (specialist остаётся None),
            # get_or_create_daily_queue ниже найдёт/создаст ресурсную
            # очередь.
            # QD-2E (RQ-15.b): ветки резолва ecg_resource/lab_resource
            # УДАЛЕНЫ (D-08) — теги покрываются реестром, а их
            # деактивация — операторское решение, не синтетик.
            if not specialist_doctor_id and not registry_tag:
                # QD-2E (Codex round-1 P2): явный владелец из услуг визита —
                # единственный distinct врач среди услуг визита с этим
                # тегом (K01 → кардиолог после operator map), проверенный
                # на пригодность (активный реальный владелец).
                visit_service_doctor_ids = {
                    int(row[0])
                    for row in (
                        self.repository.db.query(Service.doctor_id)
                        .join(
                            VisitService, VisitService.service_id == Service.id
                        )
                        .filter(
                            VisitService.visit_id == visit.id,
                            Service.queue_tag == queue_tag,
                            Service.doctor_id.isnot(None),
                        )
                        .distinct()
                        .all()
                    )
                    if row[0] is not None
                }
                if len(visit_service_doctor_ids) == 1:
                    candidate_id = next(iter(visit_service_doctor_ids))
                    if eligible_real_doctor(self.repository.db, candidate_id):
                        specialist_doctor_id = candidate_id
                    else:
                        logger.error(
                            "QD-2E fail-closed: visit_id=%s queue_tag=%s "
                            "single service doctor_id=%s is not an "
                            "eligible real owner (inactive/unlinked/"
                            "synthetic) — treating the tag as unowned (D-08)",
                            visit.id,
                            queue_tag,
                            candidate_id,
                        )
                elif len(visit_service_doctor_ids) > 1:
                    # QD-2E (Codex round-4 P2): и эта ветка — доменная
                    # ошибка подтверждения (422 + причина), не голый
                    # ValueError у PWA/Telegram-обёрток.
                    config_error = owner_configuration_error(
                        queue_tag=queue_tag,
                        detail=(
                            f"visit_id={visit.id} carries multiple explicit "
                            "service doctors for one tag — the operator "
                            "must pick one per booking"
                        ),
                    )
                    raise VisitConfirmationDomainError(
                        status_code=422,
                        detail=str(config_error),
                    ) from config_error

            if not specialist_doctor_id and not registry_tag:
                # An existing queue for this tag does not prove who should
                # perform an unowned service. D-08 requires an explicit owner.
                logger.error(
                    "QD-2E fail-closed: queue_tag=%s has no owner surface "
                    "for confirmation visit_id=%s doctor_id=%s",
                    queue_tag,
                    visit.id,
                    visit.doctor_id,
                )
                unowned_queue_tags.append(queue_tag)
                continue

            if existing_claim is not None:
                daily_queue = existing_claim.daily_queue
                existing_entry = existing_claim.entry
                self._assert_existing_claim_owner(
                    daily_queue=daily_queue,
                    specialist_id=specialist_doctor_id,
                    queue_resource_id=(
                        int(registry_resource.id)
                        if registry_surface is None and registry_resource is not None
                        else None
                    ),
                    expected_daily_queue_id=(
                        int(registry_surface.id)
                        if registry_surface is not None
                        else None
                    ),
                    queue_tag=queue_tag,
                )
                self._reuse_existing_active_entry(
                    existing_entry=existing_entry,
                    visit=visit,
                )
                queue_number = existing_entry.number
                queue_id = existing_entry.queue_id
            else:
                daily_queue = self.repository.get_or_create_daily_queue(
                    day=today,
                    specialist_id=specialist_doctor_id,
                    queue_tag=queue_tag,
                )
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
                    commit=False,
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
            # QD-2E (Codex round-2 P2): талон строится от РЕШЁННОГО
            # владельца записи — у doctorless-визита K01/K11 владельцем
            # становится врач услуги (specialist_doctor_id), а не пустой
            # visit.doctor_id (иначе талон печатал «Без врача»).
            resolved_owner_id = specialist_doctor_id or visit.doctor_id
            doctor = (
                self.repository.get_doctor(resolved_owner_id)
                if resolved_owner_id
                else None
            )
            patient = self.repository.get_patient(visit.patient_id)

            ticket_payload_extra: dict[str, Any] = {}
            if not telegram_ticket_qr_resolved:
                telegram_ticket_qr_payload = self._build_ticket_telegram_qr_payload(
                    visit
                )
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

        if unowned_queue_tags:
            # Атомарно: ни один номер не закреплён — вызывающая транзакция
            # откатывается целиком. QD-2E (Codex round-3 P2): ошибка
            # владельца — ДОМЕННАЯ ошибка подтверждения (422 с причиной и
            # путями решения), а не голый ValueError — PWA/Telegram-
            # обёртки и регистраторский путь не превращают её в 500.
            config_error = owner_configuration_error(
                queue_tag=", ".join(sorted(set(unowned_queue_tags))),
                detail=(
                    f"visit_id={visit.id} confirmation cannot resolve an "
                    "owner surface for the listed tag(s)"
                ),
            )
            raise VisitConfirmationDomainError(
                status_code=422,
                detail=str(config_error),
            ) from config_error

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
                # PR-2 (round 16): the username is only meaningful while a
                # bot credential actually resolves. Generating a ticket QR
                # link for an unresolvable bot would direct patients to a
                # revoked/compromised bot this deployment cannot operate —
                # fail closed instead (defense in depth on top of the
                # identity cleanup in telegram_token_store).
                if not resolve_patient_bot_token(self.repository.db):
                    logger.warning(
                        "Telegram bot username is configured but no bot token "
                        "resolves — skipping ticket QR link (fail-closed)"
                    )
                    return None
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
