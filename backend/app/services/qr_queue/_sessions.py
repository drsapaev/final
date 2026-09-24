"""Sessions mixin for QRQueueService.

Split from qr_queue_service.py.
"""
from __future__ import annotations

import hashlib
import json
import re
from zoneinfo import ZoneInfo

from sqlalchemy.exc import DBAPIError

from app.services.qr_queue._base import *  # noqa: F401, F403
from app.services.qr_queue._base import (
    JOIN_SESSION_JOINED_STATUS,
    JOIN_SESSION_JOINED_STATUS_V2,
    JOIN_SESSION_PROCESSING_STATUS,
    JOIN_SESSION_REASON_PAYLOAD_MISMATCH,
    JoinSessionNotExecutedRefusal,
    JoinSessionStateRefusal,
    QRQueueServiceMixinBase,
)

# Machine-readable reasons for a complete attempt that provably did NOT
# reach the business operation (round-4 review, PR #3362: P1-2 + P2-1).
JOIN_SESSION_REASON_NOT_FOUND = "join_session_not_found"
JOIN_SESSION_REASON_EXPIRED = "join_session_expired"
JOIN_SESSION_REASON_PROCESSING = "join_session_processing"
JOIN_SESSION_REASON_USED = "join_session_used"

# Round-11 (PR #3362 review, P1-2): the READ-ONLY recovery oracle's outcome
# vocabulary. ``/join/complete`` is a MUTATING endpoint — for a still-
# ``pending`` session its first claim EXECUTES the business join, so the
# ownerless-ambiguity resolution must never use it as an ownership probe.
# The probe answers the same "what is this attempt's state" question
# WITHOUT touching a single row:
#   joined_match          -> the typed payload OWNS this committed attempt
#                            (the saved result is re-served, read-only)
#   joined_mismatch       -> the attempt committed with ANOTHER payload
#                            (foreign; envelope must survive)
#   joined_owner_unknown  -> legacy committed row without a fingerprint —
#                            ownership is UNPROVABLE, fail-closed UNKNOWN
#   pending_unbound       -> the session is alive but NOTHING was ever
#                            bound/executed under it (a committed business
#                            operation would have flipped the status
#                            atomically) — provably safe to discard
#   processing            -> a claim is in flight — UNKNOWN, keep gating
#   expired / not_found   -> proven dead — the envelope guards nothing
JOIN_PROBE_OUTCOME_JOINED_MATCH = "joined_match"
JOIN_PROBE_OUTCOME_JOINED_MISMATCH = "joined_mismatch"
JOIN_PROBE_OUTCOME_JOINED_OWNER_UNKNOWN = "joined_owner_unknown"
JOIN_PROBE_OUTCOME_PENDING_UNBOUND = "pending_unbound"
JOIN_PROBE_OUTCOME_PROCESSING = "processing"
JOIN_PROBE_OUTCOME_EXPIRED = "expired"
JOIN_PROBE_OUTCOME_NOT_FOUND = "not_found"

# Round-6 (P1-1): the joined statuses the REPLAY accepts. Legacy rows
# joined by pre-round-5 workers replay fail-closed (no fingerprint ⇒ the
# used refusal); rows written by this version carry the versioned marker
# so an old worker can never mistake them for its own replayable rows.
_REPLAYABLE_JOIN_STATUSES = [
    JOIN_SESSION_JOINED_STATUS,
    JOIN_SESSION_JOINED_STATUS_V2,
]


def canonical_join_payload_fingerprint(
    patient_name: str,
    phone: str,
    telegram_id: int | None,
    specialist_ids: list[int] | None = None,
    specialist_entity_types: list[str] | None = None,
) -> str:
    """Round-5 (PR #3362 review, P1-3): the immutable payload identity of a
    complete attempt — one session token = one immutable payload.

    Canonicalization mirrors the identity rules the business operation
    itself applies (``_find_or_create_patient``: case- and
    whitespace-insensitive name, digits-only phone), so a retry that only
    reformats the SAME identity still matches, while any change of person,
    telegram id or specialist selection produces a different fingerprint.
    Untyped specialist selections canonicalize to ``doctor`` — the same
    semantics the allocator applies to a missing entity type.
    """
    from app.services.qr_queue._patients import _normalize_person_name

    canonical: dict[str, Any] = {
        "patient_name": _normalize_person_name(patient_name),
        "phone": re.sub(r"\D", "", phone or ""),
        "telegram_id": int(telegram_id) if telegram_id is not None else None,
        "specialists": None,
    }
    if specialist_ids:
        types = list(specialist_entity_types or [])
        canonical["specialists"] = [
            "{}:{}".format(
                (types[index] if index < len(types) else None) or "doctor",
                specialist_id,
            )
            for index, specialist_id in enumerate(specialist_ids)
        ]
    raw = json.dumps(
        canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SessionsMixin(QRQueueServiceMixinBase):
    """Sessions methods for QRQueueService."""

    # Round-6 (PR #3362 review, P1-3): how long past the target queue-day's
    # END the attempt identity stays recoverable. Two hours cover the
    # late-evening reconcile of a still-open desk and any client clock
    # skew; the envelope carries no PHI, so a bounded overshoot is safe.
    ATTEMPT_HORIZON_GRACE_HOURS = 2

    def _resolve_attempt_horizon(self, token: str) -> dict[str, Any]:
        """Server-computed honest horizon of a join attempt identity.

        Returns the TARGET queue-day (the QR token's own day — the same
        day ``assign_queue_token`` fixed at mint time, tomorrow when the
        start happened after the cutoff) and the absolute instant the
        attempt may finally be dropped: the end of that day in the
        clinic timezone plus the safety grace. Best-effort: an unknown
        token or an undated token yields ``None`` fields and the client
        falls back to its conservative fixed TTL.
        """
        horizon: dict[str, Any] = {
            "target_date": None,
            "attempt_expires_at": None,
        }
        try:
            token_row = (
                self.db.query(QueueToken).filter(QueueToken.token == token).first()
            )
            if token_row is None or token_row.day is None:
                return horizon
            from app.crud.clinic import get_queue_settings

            queue_settings = get_queue_settings(self.db)
            timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
            target_day = token_row.day
            # End of the target queue-day in the clinic timezone, then the
            # grace window; returned as an absolute tz-aware UTC instant.
            day_end_local = (
                datetime(target_day.year, target_day.month, target_day.day, 23, 59, 59)
                .replace(tzinfo=timezone)
                + timedelta(hours=self.ATTEMPT_HORIZON_GRACE_HOURS)
                + timedelta(seconds=1)
            )
            horizon["target_date"] = target_day
            horizon["attempt_expires_at"] = day_end_local.astimezone(UTC)
        except Exception as exc:  # noqa: BLE001 — best-effort metadata
            logger.warning(
                "[start_join_session] attempt horizon resolution failed: %s", exc
            )
        return horizon

    def _extend_joined_expires_to_horizon(self, session: QueueJoinSession) -> None:
        """Round-9 (PR #3362 review, P1-1): keep the attempt identity alive
        for ANY worker until the attempt horizon.

        On a SUCCESSFUL complete the 15-minute session TTL must not stay as
        ``expires_at``: a mixed-version OLD worker does not know the
        ``joined_v2`` marker, so once the original TTL ran out it classified
        the row through its fallback as ``join_session_expired`` — and the
        frontend treats ``expired`` as PROOF that the business operation
        never ran, offering «Start over» on top of an ALREADY COMMITTED
        талон. Extending ``expires_at`` to the same attempt horizon the
        client holds (end of the TARGET queue-day + grace) moves the row
        into the old worker's SAFE ``join_session_processing`` class for
        the whole recovery window (unknown outcome ⇒ no second business
        attempt), while the new worker keeps classifying it as ``used``
        (both joined markers are replayable state here). Never shortens an
        existing expiry; preserves the column's storage convention (SQLite
        test sessions hold naive UTC datetimes, PostgreSQL tz-aware ones).
        """
        horizon = self._resolve_attempt_horizon(session.qr_token).get(
            "attempt_expires_at"
        )
        if horizon is None:
            horizon = datetime.now(UTC) + timedelta(
                hours=self.ATTEMPT_HORIZON_GRACE_HOURS
            )
        current = session.expires_at
        if current is not None:
            current_cmp = (
                current if current.tzinfo is not None else current.replace(tzinfo=UTC)
            )
            if current_cmp > horizon:
                horizon = current_cmp
            if current.tzinfo is None:
                horizon = horizon.replace(tzinfo=None)
        session.expires_at = horizon

    def _claim_pending_join_session(self, session_token: str) -> QueueJoinSession | None:
        now_utc = datetime.now(UTC)
        pending_filter = (
            QueueJoinSession.session_token == session_token,
            QueueJoinSession.status == "pending",
            QueueJoinSession.expires_at > now_utc,
        )
        query = self.db.query(QueueJoinSession).filter(*pending_filter)

        if not hasattr(query, "update"):
            session = query.first()
            if session:
                session.status = JOIN_SESSION_PROCESSING_STATUS
                if hasattr(self.db, "flush"):
                    self.db.flush()
            return session

        updated = query.update(
            {QueueJoinSession.status: JOIN_SESSION_PROCESSING_STATUS},
            synchronize_session=False,
        )
        if updated == 0:
            return None
        if updated != 1:
            raise ValueError("Ambiguous queue join session")

        self.db.flush()
        return (
            self.db.query(QueueJoinSession)
            .filter(
                QueueJoinSession.session_token == session_token,
                QueueJoinSession.status == JOIN_SESSION_PROCESSING_STATUS,
            )
            .first()
        )

    def _classify_unclaimed_join_session(self, session_token: str) -> str:
        """PROVEN reason why the one-shot claim missed for this token.

        Round-4 (P1-2/P2-1): the pre-claim state is inspectable without
        executing any business action:
          - no row at all            -> join_session_not_found
          - pending but past TTL     -> join_session_expired
          - held by a concurrent claim -> join_session_processing
          - already joined           -> join_session_used
        """
        row = (
            self.db.query(QueueJoinSession)
            .filter(QueueJoinSession.session_token == session_token)
            .first()
        )
        if row is None:
            return JOIN_SESSION_REASON_NOT_FOUND
        if row.status in (JOIN_SESSION_JOINED_STATUS, JOIN_SESSION_JOINED_STATUS_V2):
            # Legacy ``joined`` and versioned ``joined_v2`` both mean the
            # attempt was consumed. The replay decides between the honest
            # snapshot re-serve (matching fingerprint) and the fail-closed
            # used refusal; this branch is the classifier safety net for
            # paths that reach it without a replay round-trip.
            return JOIN_SESSION_REASON_USED
        if row.status == JOIN_SESSION_PROCESSING_STATUS:
            return JOIN_SESSION_REASON_PROCESSING
        if row.expires_at is not None:
            # SQLite test sessions store naive UTC datetimes; PostgreSQL
            # stores tz-aware ones — normalize before comparing.
            expires_cmp = row.expires_at
            if expires_cmp.tzinfo is None:
                expires_cmp = expires_cmp.replace(tzinfo=UTC)
            if expires_cmp <= datetime.now(UTC):
                return JOIN_SESSION_REASON_EXPIRED
        # Pending and unexpired yet unclaimable — treat as an in-flight
        # claim (same ambiguity class as ``processing``).
        return JOIN_SESSION_REASON_PROCESSING

    def _replay_joined_session(
        self,
        session_token: str,
        patient_name: str,
        phone: str,
        telegram_id: int | None = None,
        specialist_ids: list[int] | None = None,
        specialist_entity_types: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Payload-bound replay of a joined session's saved result.

        Round-5 (PR #3362 review, P1-3): the joined session is bound to the
        payload of its FIRST successful complete. The retry must present
        the SAME identity (normalization-insensitive); a different payload
        is refused decisively with ``join_session_payload_mismatch`` — the
        attempt is never re-served to (or executed for) another identity.

        Round-5 (PR #3362 review, P2-1): the served numbers are the EXACT
        original response (the saved ``response_snapshot``), never a
        recomputed live queue picture — «результат первой попытки» means
        the numbers the patient originally received.

        Returns None when the token is not a joined session at all (the
        caller then raises the classified refusal).
        """
        row = (
            self.db.query(QueueJoinSession)
            .filter(
                QueueJoinSession.session_token == session_token,
                QueueJoinSession.status.in_(_REPLAYABLE_JOIN_STATUSES),
            )
            .first()
        )
        if row is None:
            return None

        used_refusal = JoinSessionStateRefusal(
            JOIN_SESSION_REASON_USED,
            "Сессия уже использована: результат первой попытки уже выдан",
        )
        # Legacy row joined before the payload binding existed — ownership
        # cannot be proven, so the result is never re-served (fail-closed).
        expected = row.payload_fingerprint
        if not expected:
            raise used_refusal
        actual = canonical_join_payload_fingerprint(
            patient_name,
            phone,
            telegram_id,
            specialist_ids,
            specialist_entity_types,
        )
        if expected != actual:
            raise JoinSessionStateRefusal(
                JOIN_SESSION_REASON_PAYLOAD_MISMATCH,
                "Попытка принадлежит другому набору данных",
            )
        if not row.response_snapshot:
            raise used_refusal
        try:
            snapshot = json.loads(row.response_snapshot)
        except (TypeError, ValueError):
            raise used_refusal
        if not isinstance(snapshot, dict):
            raise used_refusal

        replayed = dict(snapshot)
        replayed["replayed"] = True
        return replayed


    def start_join_session(
        self, token: str, ip_address: str = None, user_agent: str = None
    ) -> dict[str, Any]:
        """
        Начинает сессию присоединения к очереди

        Args:
            token: QR токен
            ip_address: IP адрес пользователя
            user_agent: User-Agent пользователя

        Returns:
            Данные сессии
        """
        logger.debug(
            "[QRQueueService.start_join_session] Начало сессии для токена: token_present=%s, token_length=%d",
            bool(token),
            len(token or ""),
        )

        try:
            # Проверяем токен
            token_info = self.get_qr_token_info(token)
            if not token_info:
                error_msg = "Недействительный или истекший QR токен"
                logger.debug(f"[QRQueueService.start_join_session] ❌ {error_msg}")
                raise ValueError(error_msg)

            logger.debug(
                f"[QRQueueService.start_join_session] Токен найден: queue_active={token_info.get('queue_active')}"
            )

            # Для общего QR токена разрешаем создание сессии даже если queue_active=False
            # (так как очереди могут быть еще не созданы)
            if not token_info.get("is_clinic_wide") and not token_info.get(
                "queue_active", False
            ):
                error_msg = "Очередь в данный момент не активна"
                logger.debug(f"[QRQueueService.start_join_session] ❌ {error_msg}")
                raise ValueError(error_msg)

            # Проверяем временные ограничения
            logger.debug(
                "[QRQueueService.start_join_session] Проверка временных ограничений..."
            )
            time_check = self._check_online_time_restrictions(token)
            logger.debug(
                f"[QRQueueService.start_join_session] Результат проверки времени: allowed={time_check.get('allowed')}, message={time_check.get('message')}"
            )

            if not time_check.get("allowed", False):
                error_msg = time_check.get(
                    "message", "Временные ограничения не пройдены"
                )
                logger.debug(f"[QRQueueService.start_join_session] ❌ {error_msg}")
                raise ValueError(error_msg)

            # Генерируем токен сессии
            session_token = secrets.token_urlsafe(32)

            # Создаем сессию
            session = QueueJoinSession(
                session_token=session_token,
                qr_token=token,
                patient_name="",  # Будет заполнено пользователем
                phone="",  # Будет заполнено пользователем
                ip_address=ip_address,
                user_agent=user_agent,
                expires_at=datetime.now(UTC)
                + timedelta(minutes=15),  # 15 минут на заполнение
            )

            self.db.add(session)
            self.db.commit()

            # Добавляем информацию о времени в ответ
            token_info.update(time_check)

            # Round-6 (PR #3362 review, P1-3): the attempt identity must
            # live until the END of the TARGET queue-day, not a fixed 24h
            # — a permanent-address session started after the cutoff
            # targets TOMORROW, so 24h expires while the target queue-day
            # is still running (the patient's reconcile identity would
            # disappear and a fresh start could mint a second талон for
            # the next day). The server computes the honest horizon from
            # the token's own queue day in the CLINIC timezone plus a
            # safety grace; the client stores it in the attempt envelope
            # and never auto-drops the attempt before it.
            attempt_horizon = self._resolve_attempt_horizon(token)

            return {
                "session_token": session_token,
                "expires_at": session.expires_at.isoformat(),
                "queue_info": token_info,
                "target_date": (
                    attempt_horizon["target_date"].isoformat()
                    if attempt_horizon["target_date"]
                    else None
                ),
                "attempt_expires_at": (
                    attempt_horizon["attempt_expires_at"].isoformat()
                    if attempt_horizon["attempt_expires_at"]
                    else None
                ),
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"[QRQueueService.start_join_session] КРИТИЧЕСКАЯ ОШИБКА: {e}")
            import traceback

            traceback.print_exc()
            raise ValueError("Внутренняя ошибка")


    def complete_join_session(
        self,
        session_token: str,
        patient_name: str,
        phone: str,
        telegram_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Завершает сессию присоединения к очереди

        Args:
            session_token: Токен сессии
            patient_name: ФИО пациента
            phone: Телефон пациента
            telegram_id: Telegram ID (опционально)

        Returns:
            Результат присоединения к очереди
        """
        # Находим сессию
        # expires_at сохраняется в UTC (datetime.now(UTC)), поэтому сравниваем с UTC
        session = self._claim_pending_join_session(session_token)

        if not session:
            # Round-4/5 (P1-2/P1-3): an unclaimable token is either a
            # REPLAYABLE joined session (the retry after a lost response
            # re-uses the original attempt identity AND the original
            # payload — anything else is refused) or a PROVEN
            # pre-execution refusal — classified with a machine-readable
            # reason, never a masked generic 400.
            replay = self._replay_joined_session(
                session_token,
                patient_name=patient_name,
                phone=phone,
                telegram_id=telegram_id,
            )
            if replay is not None:
                return replay
            raise JoinSessionStateRefusal(
                self._classify_unclaimed_join_session(session_token),
                "Сессия не найдена или истекла",
            )

        # Получаем информацию о токене
        qr_token = (
            self.db.query(QueueToken)
            .filter(QueueToken.token == session.qr_token)
            .first()
        )

        if not qr_token:
            self.db.rollback()
            raise ValueError("QR токен не найден")

        # ⭐ FIX: Создаём или находим пациента (patient_id ВСЕГДА заполняется)
        patient = self._find_or_create_patient(patient_name, phone)
        patient_id = patient.id if patient else None

        if not patient_id:
            logger.warning(
                "[complete_join_session] ⚠️ Не удалось создать/найти пациента"
            )

        try:
            # Round-5 (PR #3362 review, P1-2): the allocator runs WITHOUT
            # its own commit. Claim, patient resolution, the талон and the
            # joined outcome share ONE transaction boundary: a crash after
            # the entry is created no longer strands a committed ticket
            # under a permanently-``joining`` session — either the whole
            # attempt commits, or nothing did and the same token re-runs.
            join_result = self.queue_domain_service.allocate_ticket(
                allocation_mode="join_with_token",
                token_str=qr_token.token,
                patient_name=patient_name,
                phone=phone,
                telegram_id=telegram_id,
                patient_id=patient_id,  # ⭐ Теперь ВСЕГДА заполнен
                source="online",
                commit=False,
            )
        except (QueueValidationError, QueueConflictError, QueueNotFoundError) as exc:
            self.db.rollback()
            # Round-6 (P2-1): the rollback is CONFIRMED — nothing reached
            # the database. The refusal says so explicitly instead of
            # being masked behind «Internal server error».
            raise JoinSessionNotExecutedRefusal(
                str(exc),
                details=[{"specialist_id": None, "error": str(exc)}],
            ) from exc

        queue_entry = join_result["entry"]
        queue_length_before = join_result["queue_length_before"]
        estimated_wait = join_result["estimated_wait_minutes"]

        # ✅ Получаем имя врача правильно (из User)
        specialist_name = join_result.get("specialist_name")
        if not specialist_name:
            specialist_name = f"Врач ID {qr_token.specialist_id}"

        response = {
            "success": True,
            "queue_number": queue_entry.number,
            "queue_length": queue_length_before,  # ✅ Значение ДО добавления
            "estimated_wait_time": estimated_wait,
            "specialist_name": specialist_name,
            "department": qr_token.department,
        }

        # Обновляем сессию
        # Round-6 (P1-1): the versioned joined marker — an old worker
        # never treats this row as ITS replayable state (mixed-version
        # wrong-patient replay barrier; see _base.py).
        session.status = JOIN_SESSION_JOINED_STATUS_V2
        session.patient_name = patient_name
        session.phone = phone
        session.telegram_id = telegram_id
        session.queue_entry_id = queue_entry.id
        session.queue_number = queue_entry.number
        session.joined_at = datetime.now(UTC)
        # Round-5 (P1-3/P2-1): the immutable payload binding and the exact
        # response snapshot are written in the SAME transaction as the
        # joined status — one commit, one atomic outcome.
        session.payload_fingerprint = canonical_join_payload_fingerprint(
            patient_name, phone, telegram_id
        )
        session.response_snapshot = json.dumps(
            response, ensure_ascii=False, default=str
        )
        # Round-9 (PR #3362 review, P1-1): the successful complete moves the
        # row's expiry to the attempt horizon — a mixed-version OLD worker
        # must classify this row as the SAFE ``join_session_processing``
        # for the whole recovery window, never as the start-over-safe
        # ``join_session_expired`` on top of a COMMITTED талон.
        self._extend_joined_expires_to_horizon(session)

        self.db.commit()

        # Round-5 (P1-4): post-commit side effects are best-effort. The
        # business operation is already durably committed — a statistics
        # or broadcast failure must never surface a 500 the client would
        # (mis)classify as «rolled back».
        if not join_result["duplicate"]:
            try:
                self._update_queue_statistics(queue_entry.queue_id, "online_joins")
            except Exception as exc:
                self.db.rollback()
                logger.warning(
                    "[complete_join_session] Failed to update statistics: %s",
                    exc,
                )
            try:
                from app.services.display_websocket import (
                    dispatch_async,
                    get_display_manager,
                )

                manager = get_display_manager()
                dispatch_async(
                    manager.broadcast_queue_update(
                        queue_entry=queue_entry,
                        event_type="queue.created",
                    )
                )
            except Exception as exc:
                logger.warning(
                    "[complete_join_session] Failed to broadcast queue.created: %s",
                    exc,
                )

        return response


    def complete_join_session_multiple(
        self,
        session_token: str,
        specialist_ids: list[int],
        patient_name: str,
        phone: str,
        telegram_id: int | None = None,
        specialist_entity_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Завершает сессию присоединения для нескольких специалистов (общий QR).

        RQ-09.b (D-01 APPROVED 2026-09-15): тип каждой сущности в
        ``specialist_ids`` передаётся ЯВНО через ``specialist_entity_types``
        (выровнен по индексам; значения 'doctor' | 'profile') и никогда не
        выводится из совпадения числового ID.
        """
        if not specialist_ids:
            raise ValueError("Не выбраны специалисты для записи")

        normalized_entity_types: list[str] | None = None
        if specialist_entity_types is not None:
            if len(specialist_entity_types) != len(specialist_ids):
                raise ValueError(
                    "specialist_entity_types должен соответствовать specialist_ids по длине"
                )
            allowed_types = {"doctor", "profile"}
            normalized_entity_types = [
                str(entity_type).strip().lower()
                for entity_type in specialist_entity_types
            ]
            unknown = [
                entity_type
                for entity_type in normalized_entity_types
                if entity_type not in allowed_types
            ]
            if unknown:
                raise ValueError(
                    f"Недопустимый тип специалиста: {', '.join(sorted(set(unknown)))}"
                )

        # expires_at сохраняется в UTC (datetime.now(UTC)), поэтому сравниваем с UTC
        session = self._claim_pending_join_session(session_token)

        if not session:
            # Round-4/5 (P1-2/P1-3): same contract as the single path — a
            # joined session replays its saved ticket ONLY to the payload
            # that created it; everything else refuses with a PROVEN
            # machine-readable reason.
            replay = self._replay_joined_session(
                session_token,
                patient_name=patient_name,
                phone=phone,
                telegram_id=telegram_id,
                specialist_ids=specialist_ids,
                specialist_entity_types=normalized_entity_types,
            )
            if replay is not None:
                return replay
            raise JoinSessionStateRefusal(
                self._classify_unclaimed_join_session(session_token),
                "Сессия не найдена или истекла",
            )

        qr_token = (
            self.db.query(QueueToken)
            .filter(QueueToken.token == session.qr_token)
            .first()
        )
        if not qr_token:
            self.db.rollback()
            raise ValueError("QR токен не найден")

        # Round-8 (PR #3362 review, P2-3): the PATIENT phone lock moves
        # BEFORE the batch tag-scope pre-lock — restoring the SINGLE
        # canonical order phone → sorted tag scopes across BOTH paths.
        # The single path already acquires the phone advisory lock here
        # (via _find_or_create_patient) and only later takes the tag-claim
        # scope inside the allocator; the round-6 multi pre-lock introduced
        # the opposite order (sorted tags → phone), a live AB-BA cycle
        # between a single and a multi join of the same phone/day (the
        # transaction-scoped pg_advisory_xact_lock('qr_patient:{phone}')
        # vs the daily_queue tag scopes). With the phone lock first, two
        # multi joins serialize on the phone only when the phone matches
        # and then proceed in the sorted-tag canon; a single vs a multi no
        # longer close a cycle. Patient creation is unconditional before
        # the allocation loop either way, so hoisting it across the
        # best-effort pre-lock (which never aborts the attempt) changes no
        # outcome contract — only the acquisition order of the same locks.
        # ⭐ FIX: Создаём или находим пациента (patient_id ВСЕГДА заполняется)
        patient = self._find_or_create_patient(patient_name, phone)
        patient_id = patient.id if patient else None

        if not patient_id:
            logger.warning(
                "[complete_join_session_multiple] ⚠️ Не удалось создать/найти пациента"
            )

        # Round-6 (PR #3362 review, P1-2): canonical multi-tag lock order.
        # Every allocation of the batch now holds its transaction-scoped
        # tag-claim scope until the ONE final commit, so two concurrent
        # multi-joins with the same directions in INVERTED input order
        # used to acquire the ``daily_queue:tag:<tag>:<day>`` advisory
        # scopes in opposite orders — the exact AB-BA deadlock the
        # QD-2E canon (lock_queue_tag_claim_scope) forbids. The batch
        # pre-resolves every selection's claim scope READ-ONLY and
        # pre-acquires all scopes in sorted ``(day, queue_tag)`` order
        # BEFORE the first write (the same restore-of-order the
        # registrar cart's prelock_cart_tag_claim_scopes performs), then
        # allocates in the same sorted order. Unresolvable selections are
        # skipped here — the allocation loop reports their real error.
        # Round-8 (P2-3): this whole block now runs AFTER the phone lock
        # above — phone → sorted tags is the shared canon of both paths.
        try:
            resolved_targets = (
                self.queue_domain_service.allocator_service
                .resolve_join_batch_tag_targets(
                    self.db,
                    token_str=qr_token.token,
                    specialist_ids=specialist_ids,
                    specialist_entity_types=normalized_entity_types,
                )
            )
            # Defensive shape check: the resolver must return an
            # index->tag mapping; anything else disables the canonical
            # order but never the attempt itself.
            batch_lock_targets = (
                resolved_targets
                if isinstance(resolved_targets, dict)
                and all(
                    isinstance(k, int) and isinstance(v, str)
                    for k, v in resolved_targets.items()
                )
                else {}
            )
            self.queue_domain_service.allocator_service.prelock_join_batch_tag_scopes(
                self.db,
                lock_targets=batch_lock_targets,
                token_str=qr_token.token,
            )
        except Exception as exc:  # noqa: BLE001 — pre-lock is best-effort
            logger.warning(
                "[complete_join_session_multiple] tag scope pre-lock skipped: %s",
                exc,
            )
            batch_lock_targets = {}

        def _batch_lock_key(index: int) -> tuple[str, int]:
            # Canonical acquisition order: sorted tag first (the same key
            # the pre-locks used), original input order as the stable
            # tie-break. Unresolvable targets sort last but keep their
            # relative input order.
            tag = batch_lock_targets.get(index)
            return (tag or "\uffff", index)

        # Round-8 (P2-3): the patient block moved ABOVE the tag-scope
        # pre-lock (phone → sorted tags, the single-path order).

        entries: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        created_entries: list[OnlineQueueEntry] = []
        # Round-6 (P1-2): allocations run in the canonical lock order, but
        # the response/fingerprint keep the USER's original selection
        # order — results are reassembled by index after the loop.
        entries_by_index: dict[int, dict[str, Any]] = {}
        errors_by_index: dict[int, dict[str, Any]] = {}

        for index in sorted(range(len(specialist_ids)), key=_batch_lock_key):
            specialist_id = specialist_ids[index]
            specialist_type = (
                normalized_entity_types[index]
                if normalized_entity_types is not None
                else None
            )
            try:
                # Round-5 (PR #3362 review, P1-2): no allocator commit and
                # no mid-loop statistics commit — every allocation of the
                # batch and the joined outcome share ONE final transaction
                # boundary. A mid-batch failure rolls the whole attempt
                # back instead of stranding committed entries under a
                # ``joining`` session.
                join_result = self.queue_domain_service.allocate_ticket(
                    allocation_mode="join_with_token",
                    token_str=qr_token.token,
                    patient_name=patient_name,
                    phone=phone,
                    telegram_id=telegram_id,
                    patient_id=patient_id,  # ⭐ Теперь ВСЕГДА заполнен
                    specialist_id_override=specialist_id,
                    specialist_type=specialist_type,
                    source="online",
                    commit=False,
                )
                entry = join_result["entry"]
                entries_by_index[index] = {
                    "specialist_id": specialist_id,
                    "queue_entry_id": entry.id,
                    "queue_number": entry.number,
                    "duplicate": join_result["duplicate"],
                    "queue_length": join_result["queue_length_before"],
                    "estimated_wait_time": join_result["estimated_wait_minutes"],
                    "specialist_name": join_result.get("specialist_name"),
                    "department": qr_token.department,
                }
                if not join_result["duplicate"]:
                    created_entries.append(entry)
            except (
                QueueValidationError,
                QueueConflictError,
                QueueNotFoundError,
            ) as exc:
                errors_by_index[index] = {
                    "specialist_id": specialist_id,
                    "error": str(exc),
                }

        # Restore the USER's original order (input-index ascending) for
        # both the response entries and the per-specialist error list.
        entries = [
            entries_by_index[i] for i in sorted(entries_by_index)
        ]
        errors = [errors_by_index[i] for i in sorted(errors_by_index)]

        if errors and not entries:
            self.db.rollback()
            # Round-6 (PR #3362 review, P2-1): the rollback is CONFIRMED —
            # the batch provably created NO ticket. A structured, typed
            # refusal replaces the masked «Internal server error» 400:
            # the client may offer the honest start-over immediately
            # instead of looping on UNKNOWN until the session TTL.
            raise JoinSessionNotExecutedRefusal(
                errors[0]["error"], details=errors
            )

        response = {
            "success": len(entries) > 0,
            "queue_time": datetime.now(UTC).isoformat(),
            "entries": entries,
            "errors": errors or None,
            "message": f"Создано {len(entries)} записей, ошибок: {len(errors)}",
        }

        # Round-6 (P1-1): the versioned joined marker (see the single
        # path) — an old worker never treats this row as ITS replayable
        # state; the response restores the USER's original selection
        # order regardless of the canonical lock/allocation order.
        session.status = JOIN_SESSION_JOINED_STATUS_V2
        session.patient_name = patient_name
        session.phone = phone
        session.telegram_id = telegram_id
        session.queue_entry_id = entries[0]["queue_entry_id"] if entries else None
        session.queue_number = entries[0]["queue_number"] if entries else None
        session.joined_at = datetime.now(UTC)
        # Round-5 (P1-3/P2-1): the payload binding + exact response
        # snapshot — same single transaction as the joined status.
        session.payload_fingerprint = canonical_join_payload_fingerprint(
            patient_name,
            phone,
            telegram_id,
            specialist_ids,
            normalized_entity_types,
        )
        session.response_snapshot = json.dumps(
            response, ensure_ascii=False, default=str
        )
        # Round-9 (PR #3362 review, P1-1): same horizon extension as the
        # single path — the old worker keeps the SAFE ``processing`` class
        # until the attempt horizon ends.
        self._extend_joined_expires_to_horizon(session)
        self.db.commit()

        # Round-5 (P1-4): post-commit side effects are best-effort —
        # previously the per-entry statistics commits ran BEFORE the
        # outcome commit and could both strand the ``joining`` mid-state
        # and 500 the client after the business operation had landed.
        if created_entries:
            for created_entry in created_entries:
                try:
                    self._update_queue_statistics(
                        created_entry.queue_id, "online_joins"
                    )
                except Exception as exc:
                    self.db.rollback()
                    logger.warning(
                        "[complete_join_session_multiple] Failed to update statistics: %s",
                        exc,
                    )
            try:
                from app.services.display_websocket import (
                    dispatch_async,
                    get_display_manager,
                )

                manager = get_display_manager()
                for entry in created_entries:
                    dispatch_async(
                        manager.broadcast_queue_update(
                            queue_entry=entry,
                            event_type="queue.created",
                        )
                    )
            except Exception as exc:
                logger.warning(
                    "[complete_join_session_multiple] Failed to broadcast queue.created: %s",
                    exc,
                )

        return response

    def probe_join_session(
        self,
        session_token: str,
        patient_name: str,
        phone: str,
        telegram_id: int | None = None,
        specialist_ids: list[int] | None = None,
        specialist_entity_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Round-11 (PR #3362 review, P1-2): READ-ONLY recovery oracle.

        The ownerless-ambiguity resolution (round-10) asks the patient to
        «check» each outstanding attempt with their typed identity. With
        ``/join/complete`` that check was the MUTATION itself: for a still
        ``pending`` session (the original request may never have reached
        the server) the probe-complete claimed the row and EXECUTED the
        business join with the typed payload — a second бизнес-заход for a
        patient whose real attempt may already be committed elsewhere.

        This oracle answers the ownership question WITHOUT any mutation:
        no claim, no patient resolution, no талон allocation, no status or
        expiry write. It classifies the row against the typed payload and
        (for a matching committed attempt) re-serves the EXACT saved
        response snapshot — the same bytes a payload-bound replay would
        return, minus the write path.

        The classification decision table lives in the module docstring of
        the ``JOIN_PROBE_OUTCOME_*`` constants above.

        Round-12 (PR #3362 review, P1): the oracle must also be
        CONCURRENCY-SAFE. Between the claim (``UPDATE pending -> joining``)
        and the single COMMIT the complete transaction HOLDS the row lock
        while the last COMMITTED version of the row is still ``pending``.
        Under MVCC a plain SELECT would read that stale committed version
        and classify an IN-FLIGHT business join as ``pending_unbound``
        (or, near TTL, as ``expired``) — the ambiguity panel would then
        offer the discard of an attempt that is about to commit, and a
        fresh start could ride on top of the first attempt's талон.
        Therefore the row is read ``FOR UPDATE NOWAIT``: a concurrent
        complete surfaces as PostgreSQL ``55P03 lock_not_available``, and
        the probe answers the honest UNKNOWN (``processing``) instead of
        any dead/discarding class. When no complete is in flight the lock
        is granted instantly and the classification below runs on the
        decisive committed state (``joined_v2`` after a commit, ``pending``
        after a rollback). SQLite ignores ``FOR UPDATE`` (single writer,
        no MVCC race), so the committed-state classes stay testable there
        unchanged.
        """
        try:
            row = (
                self.db.query(QueueJoinSession)
                .filter(QueueJoinSession.session_token == session_token)
                .populate_existing()
                .with_for_update(nowait=True)
                .first()
            )
        except DBAPIError as exc:
            # psycopg 3 exposes the SQLSTATE as ``sqlstate`` (psycopg 2
            # historically as ``pgcode``) — check both so the mapping
            # survives a driver swap.
            orig = getattr(exc, "orig", None)
            sqlstate = getattr(orig, "sqlstate", None) or getattr(
                orig, "pgcode", None
            )
            if sqlstate == "55P03":  # lock_not_available
                # A concurrent complete holds the claim — the business
                # operation is IN FLIGHT. No decisive classification is
                # possible (and none is needed): UNKNOWN keeps every
                # envelope intact and forbids both discard and start-over.
                return {
                    "outcome": JOIN_PROBE_OUTCOME_PROCESSING,
                    "result": None,
                }
            raise
        if row is None:
            return {
                "outcome": JOIN_PROBE_OUTCOME_NOT_FOUND,
                "result": None,
            }

        if row.status in (JOIN_SESSION_JOINED_STATUS, JOIN_SESSION_JOINED_STATUS_V2):
            # Legacy row joined before the payload binding existed —
            # ownership cannot be proven, so NOTHING is re-served
            # (fail-closed, the same decision the replay makes).
            expected = row.payload_fingerprint
            if not expected:
                return {
                    "outcome": JOIN_PROBE_OUTCOME_JOINED_OWNER_UNKNOWN,
                    "result": None,
                }
            actual = canonical_join_payload_fingerprint(
                patient_name,
                phone,
                telegram_id,
                specialist_ids,
                specialist_entity_types,
            )
            if expected != actual:
                return {
                    "outcome": JOIN_PROBE_OUTCOME_JOINED_MISMATCH,
                    "result": None,
                }
            if not row.response_snapshot:
                # A committed attempt whose snapshot was lost cannot prove
                # WHAT was served — fail closed rather than re-serving a
                # fabricated picture.
                return {
                    "outcome": JOIN_PROBE_OUTCOME_JOINED_OWNER_UNKNOWN,
                    "result": None,
                }
            try:
                snapshot = json.loads(row.response_snapshot)
            except (TypeError, ValueError):
                return {
                    "outcome": JOIN_PROBE_OUTCOME_JOINED_OWNER_UNKNOWN,
                    "result": None,
                }
            if not isinstance(snapshot, dict):
                return {
                    "outcome": JOIN_PROBE_OUTCOME_JOINED_OWNER_UNKNOWN,
                    "result": None,
                }
            replayed = dict(snapshot)
            replayed["replayed"] = True
            return {
                "outcome": JOIN_PROBE_OUTCOME_JOINED_MATCH,
                "result": replayed,
            }

        if row.status == JOIN_SESSION_PROCESSING_STATUS:
            return {
                "outcome": JOIN_PROBE_OUTCOME_PROCESSING,
                "result": None,
            }

        if row.expires_at is not None:
            # SQLite test sessions store naive UTC datetimes; PostgreSQL
            # stores tz-aware ones — normalize before comparing.
            expires_cmp = row.expires_at
            if expires_cmp.tzinfo is None:
                expires_cmp = expires_cmp.replace(tzinfo=UTC)
            if expires_cmp <= datetime.now(UTC):
                return {
                    "outcome": JOIN_PROBE_OUTCOME_EXPIRED,
                    "result": None,
                }

        # ``pending`` and unexpired: nothing was ever bound under this
        # session (the fingerprint is written atomically WITH the joined
        # status), so no business operation has committed here — provably
        # safe to discard the envelope and start fresh.
        return {
            "outcome": JOIN_PROBE_OUTCOME_PENDING_UNBOUND,
            "result": None,
        }


