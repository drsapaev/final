"""Sessions mixin for QRQueueService.

Split from qr_queue_service.py.
"""
from __future__ import annotations

from app.services.qr_queue._base import *  # noqa: F401, F403
from app.services.qr_queue._base import QRQueueServiceMixinBase


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
            raise ValueError("Сессия не найдена или истекла")

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
    ) -> dict[str, Any]:
        """
        Завершает сессию присоединения для нескольких специалистов (общий QR).
        """
        if not specialist_ids:
            raise ValueError("Не выбраны специалисты для записи")

        # expires_at сохраняется в UTC (datetime.now(UTC)), поэтому сравниваем с UTC
        session = self._claim_pending_join_session(session_token)

        if not session:
            raise ValueError("Сессия не найдена или истекла")

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

        for specialist_id in specialist_ids:
            try:
                join_result = self.queue_domain_service.allocate_ticket(
                    allocation_mode="join_with_token",
                    token_str=qr_token.token,
                    patient_name=patient_name,
                    phone=phone,
                    telegram_id=telegram_id,
                    patient_id=patient_id,  # ⭐ Теперь ВСЕГДА заполнен
                    specialist_id_override=specialist_id,
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


