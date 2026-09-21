"""Sessions mixin for QRQueueService.

Split from qr_queue_service.py.
"""
from __future__ import annotations

from app.services.qr_queue._base import *  # noqa: F401, F403
from app.services.qr_queue._base import (
    JOIN_SESSION_PROCESSING_STATUS,
    JoinSessionStateRefusal,
    QRQueueServiceMixinBase,
)

# Machine-readable reasons for a complete attempt that provably did NOT
# reach the business operation (round-4 review, PR #3362: P1-2 + P2-1).
JOIN_SESSION_REASON_NOT_FOUND = "join_session_not_found"
JOIN_SESSION_REASON_EXPIRED = "join_session_expired"
JOIN_SESSION_REASON_PROCESSING = "join_session_processing"
JOIN_SESSION_REASON_USED = "join_session_used"


class SessionsMixin(QRQueueServiceMixinBase):
    """Sessions methods for QRQueueService."""

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
        if row.status == "joined":
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

    def _resolve_entry_specialist_name(self, entry: OnlineQueueEntry | None) -> str:
        """Best-effort owner name for a replayed ticket (registry axis
        first — the same precedence the join metadata uses)."""
        if entry is None:
            return ""
        queue: DailyQueue | None = entry.queue
        if queue is not None and queue.queue_resource_id is not None:
            resource = queue.queue_resource
            return (resource.display_name if resource is not None else "") or "Ресурс очереди"
        if queue is not None and queue.specialist_id:
            doctor = (
                self.db.query(Doctor)
                .filter(Doctor.id == queue.specialist_id)
                .first()
            )
            if doctor is not None and doctor.user is not None and doctor.user.full_name:
                return doctor.user.full_name
        return ""

    def _replay_active_queue_metrics(self, entry: OnlineQueueEntry) -> tuple[int, int]:
        """Current (waiting|called) length and the matching wait estimate
        for a replayed ticket — the same filters the fresh join uses for
        ``queue_length_before``."""
        active_length = (
            self.db.query(func.count(OnlineQueueEntry.id))
            .filter(
                OnlineQueueEntry.queue_id == entry.queue_id,
                OnlineQueueEntry.status.in_(["waiting", "called"]),
            )
            .scalar()
            or 0
        )
        try:
            from app.crud.clinic import get_queue_settings

            avg_minutes = int(
                (get_queue_settings(self.db) or {}).get("estimated_wait_minutes", 15)
            )
        except Exception:  # pragma: no cover — settings are advisory here
            avg_minutes = 15
        return active_length, active_length * avg_minutes

    def _replay_joined_session_single(
        self,
        session: QueueJoinSession,
        qr_token: QueueToken | None,
    ) -> dict[str, Any]:
        """Idempotent re-serve of a joined session's saved ticket result.

        Round-4 (P1-2, server-side hardening): after a lost complete
        response the patient's retry re-uses the ORIGINAL attempt identity
        (the same session token). A joined session replays its saved
        result instead of refusing — the retry becomes decisive in both
        directions (replayed ticket OR proven expired) and can never
        mint a second business attempt.
        """
        entry: OnlineQueueEntry | None = None
        if session.queue_entry_id:
            entry = (
                self.db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.id == session.queue_entry_id)
                .first()
            )
        active_length, estimated_wait = (
            self._replay_active_queue_metrics(entry)
            if entry is not None
            else (0, 0)
        )
        return {
            "success": True,
            "queue_number": entry.number if entry is not None else session.queue_number,
            "queue_length": active_length,
            "estimated_wait_time": estimated_wait,
            "specialist_name": self._resolve_entry_specialist_name(entry),
            "department": (qr_token.department if qr_token is not None else "") or "",
            "replayed": True,
        }

    def _replay_joined_session_multiple(
        self,
        session: QueueJoinSession,
        qr_token: QueueToken | None,
        specialist_ids: list[int] | None,
    ) -> dict[str, Any]:
        """Replay for the multi-specialist complete surface.

        A direction-scoped session (the permanent /q/<code> route) joins
        EXACTLY ONE profile — its replay is exact from the saved entry.
        A legacy clinic-wide join of N specialists is NOT exactly
        reconstructible from the session row (only the first entry is
        saved), so it refuses with the honest ``join_session_used``
        reason instead of guessing.
        """
        direction_scoped = bool(
            qr_token is not None
            and qr_token.is_clinic_wide
            and (qr_token.department or "").startswith(queue_service.PUBLIC_ADDRESS_DEPARTMENT_PREFIX)
        )
        if not direction_scoped:
            raise JoinSessionStateRefusal(
                JOIN_SESSION_REASON_USED,
                "Сессия уже использована: результат первой попытки уже выдан",
            )

        entry: OnlineQueueEntry | None = None
        if session.queue_entry_id:
            entry = (
                self.db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.id == session.queue_entry_id)
                .first()
            )
        if entry is None:
            # The saved ticket no longer exists — nothing honest to replay.
            raise JoinSessionStateRefusal(
                JOIN_SESSION_REASON_USED,
                "Сессия уже использована: результат первой попытки уже выдан",
            )
        active_length, estimated_wait = self._replay_active_queue_metrics(entry)
        replayed_entry = {
            "specialist_id": (specialist_ids or [None])[0],
            "queue_entry_id": entry.id,
            "queue_number": entry.number,
            "duplicate": True,
            "queue_length": active_length,
            "estimated_wait_time": estimated_wait,
            "specialist_name": self._resolve_entry_specialist_name(entry),
            "department": (qr_token.department if qr_token is not None else "") or "",
        }
        return {
            "success": True,
            "queue_time": (entry.queue_time or datetime.now(UTC)).isoformat(),
            "entries": [replayed_entry],
            "errors": None,
            "message": "Повторный запрос: результат первой попытки",
            "replayed": True,
        }

    def _replay_joined_session(
        self,
        session_token: str,
        specialist_ids: list[int] | None = None,
    ) -> dict[str, Any] | None:
        """Return a replayable saved result for a joined session, or None
        when the token is not a joined session at all (the caller then
        raises the classified refusal)."""
        row = (
            self.db.query(QueueJoinSession)
            .filter(
                QueueJoinSession.session_token == session_token,
                QueueJoinSession.status == "joined",
            )
            .first()
        )
        if row is None:
            return None
        qr_token = (
            self.db.query(QueueToken)
            .filter(QueueToken.token == row.qr_token)
            .first()
        )
        if specialist_ids:
            return self._replay_joined_session_multiple(row, qr_token, specialist_ids)
        return self._replay_joined_session_single(row, qr_token)


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

            return {
                "session_token": session_token,
                "expires_at": session.expires_at.isoformat(),
                "queue_info": token_info,
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
            # Round-4 (P1-2/P2-1): an unclaimable token is either a
            # REPLAYABLE joined session (the retry after a lost response
            # re-uses the original attempt identity) or a PROVEN
            # pre-execution refusal — classified with a machine-readable
            # reason, never a masked generic 400.
            replay = self._replay_joined_session(session_token)
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
            join_result = self.queue_domain_service.allocate_ticket(
                allocation_mode="join_with_token",
                token_str=qr_token.token,
                patient_name=patient_name,
                phone=phone,
                telegram_id=telegram_id,
                patient_id=patient_id,  # ⭐ Теперь ВСЕГДА заполнен
                source="online",
            )
        except (QueueValidationError, QueueConflictError, QueueNotFoundError) as exc:
            self.db.rollback()
            raise ValueError(str(exc)) from exc

        queue_entry = join_result["entry"]
        queue_length_before = join_result["queue_length_before"]
        estimated_wait = join_result["estimated_wait_minutes"]

        # Обновляем сессию
        session.status = "joined"
        session.patient_name = patient_name
        session.phone = phone
        session.telegram_id = telegram_id
        session.queue_entry_id = queue_entry.id
        session.queue_number = queue_entry.number
        session.joined_at = datetime.now(UTC)

        self.db.commit()

        if not join_result["duplicate"]:
            self._update_queue_statistics(queue_entry.queue_id, "online_joins")
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

        # ✅ Получаем имя врача правильно (из User)
        specialist_name = join_result.get("specialist_name")
        if not specialist_name:
            specialist_name = f"Врач ID {qr_token.specialist_id}"

        return {
            "success": True,
            "queue_number": queue_entry.number,
            "queue_length": queue_length_before,  # ✅ Используем сохраненное значение ДО добавления
            "estimated_wait_time": estimated_wait,
            "specialist_name": specialist_name,
            "department": qr_token.department,
        }


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
            # Round-4 (P1-2/P2-1): same contract as the single path — a
            # joined direction session replays its saved ticket; everything
            # else refuses with a PROVEN machine-readable reason.
            replay = self._replay_joined_session(session_token, specialist_ids)
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

        # ⭐ FIX: Создаём или находим пациента (patient_id ВСЕГДА заполняется)
        patient = self._find_or_create_patient(patient_name, phone)
        patient_id = patient.id if patient else None

        if not patient_id:
            logger.warning(
                "[complete_join_session_multiple] ⚠️ Не удалось создать/найти пациента"
            )

        entries: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        created_entries: list[OnlineQueueEntry] = []

        for index, specialist_id in enumerate(specialist_ids):
            specialist_type = (
                normalized_entity_types[index]
                if normalized_entity_types is not None
                else None
            )
            try:
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
                )
                entry = join_result["entry"]
                entries.append(
                    {
                        "specialist_id": specialist_id,
                        "queue_entry_id": entry.id,
                        "queue_number": entry.number,
                        "duplicate": join_result["duplicate"],
                        "queue_length": join_result["queue_length_before"],
                        "estimated_wait_time": join_result["estimated_wait_minutes"],
                        "specialist_name": join_result.get("specialist_name"),
                        "department": qr_token.department,
                    }
                )
                if not join_result["duplicate"]:
                    self._update_queue_statistics(entry.queue_id, "online_joins")
                    created_entries.append(entry)
            except (
                QueueValidationError,
                QueueConflictError,
                QueueNotFoundError,
            ) as exc:
                errors.append(
                    {
                        "specialist_id": specialist_id,
                        "error": str(exc),
                    }
                )

        if errors and not entries:
            self.db.rollback()
            raise ValueError(errors[0]["error"])

        session.status = "joined"
        session.patient_name = patient_name
        session.phone = phone
        session.telegram_id = telegram_id
        session.queue_entry_id = entries[0]["queue_entry_id"] if entries else None
        session.queue_number = entries[0]["queue_number"] if entries else None
        session.joined_at = datetime.now(UTC)
        self.db.commit()

        if created_entries:
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

        return {
            "success": len(entries) > 0,
            "queue_time": datetime.now(UTC).isoformat(),
            "entries": entries,
            "errors": errors or None,
            "message": f"Создано {len(entries)} записей, ошибок: {len(errors)}",
        }


