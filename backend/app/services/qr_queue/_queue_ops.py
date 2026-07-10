"""Queue_Ops mixin for QRQueueService.

Split from qr_queue_service.py.
"""
from __future__ import annotations

from app.services.qr_queue._base import *  # noqa: F401, F403
from app.services.qr_queue._base import QRQueueServiceMixinBase, _now


class QueueOpsMixin(QRQueueServiceMixinBase):
    """Queue_Ops methods for QRQueueService."""

    def get_queue_status(
        self, specialist_id: int, target_date: date = None
    ) -> dict[str, Any]:
        """
        Получает статус очереди специалиста

        Args:
            specialist_id: ID специалиста
            target_date: Дата (по умолчанию сегодня)

        Returns:
            Статус очереди
        """
        if target_date is None:
            target_date = date.today()

        daily_queue = (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.day == target_date, DailyQueue.specialist_id == specialist_id
            )
            .first()
        )

        if not daily_queue:
            return {
                "active": False,
                "queue_length": 0,
                "current_number": None,
                "entries": [],
            }

        # Получаем записи в очереди
        entries = (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == daily_queue.id)
            .order_by(OnlineQueueEntry.number)
            .all()
        )

        # Находим текущий номер (последний вызванный или обслуженный)
        current_number = None
        last_served = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.status.in_(["called", "served"]),
            )
            .order_by(OnlineQueueEntry.number.desc())
            .first()
        )

        if last_served:
            current_number = last_served.number

        return {
            "active": daily_queue.active,
            "queue_length": len(
                [e for e in entries if e.status in ["waiting", "called"]]
            ),
            "current_number": current_number,
            "entries": [
                {
                    "number": entry.number,
                    "patient_name": entry.patient_name,
                    "status": entry.status,
                    "source": entry.source,
                    "created_at": (
                        entry.created_at.isoformat() if entry.created_at else None
                    ),
                }
                for entry in entries
            ],
        }

    # ============================================================
    # === QUEUE OPERATIONS ===
    # ============================================================


    def call_next_patient(
        self,
        specialist_id: int,
        called_by_user_id: int,
        target_date: date | None = None,
    ) -> dict[str, Any]:
        """
        Вызывает следующего пациента в очереди

        Args:
            specialist_id: ID специалиста
            called_by_user_id: ID пользователя, вызвавшего пациента
            target_date: Дата очереди (по умолчанию сегодня)

        Returns:
            Информация о вызванном пациенте
        """
        queue_date = target_date if target_date else date.today()
        daily_queue = (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.day == queue_date,
                DailyQueue.specialist_id == specialist_id,
                DailyQueue.active == True,
            )
            .first()
        )

        if not daily_queue:
            raise ValueError(f"Очередь не активна на дату {queue_date}")

        # Находим следующего пациента в статусе "waiting"
        # QUEUE-AUDIT-28 P0-7: with_for_update() — защита от race condition.
        # Раньше два врача могли одновременно вызвать одного пациента.
        next_patient = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.status == "waiting",
            )
            .order_by(OnlineQueueEntry.number)
            .with_for_update()
            .first()
        )

        if not next_patient:
            return {"success": False, "message": "Нет пациентов в очереди"}

        # Обновляем статус
        next_patient.status = "called"
        next_patient.called_at = datetime.now(UTC)
        next_patient.called_by_user_id = called_by_user_id

        self.db.commit()

        return {
            "success": True,
            "patient": {
                "id": next_patient.id,
                "number": next_patient.number,
                "name": next_patient.patient_name,
                "phone": next_patient.phone,
                "source": next_patient.source,
            },
            "queue_length": self._get_queue_length(daily_queue.id),
        }

    # ============================================================
    # === TOKEN QUERIES ===
    # ============================================================


    def _get_queue_length(self, queue_id: int) -> int:
        """
        Получает текущую длину очереди (только OnlineQueueEntry).

        ⭐ ИСПРАВЛЕНО: Для онлайн-очереди считаем только записи OnlineQueueEntry,
        а не Visit/Appointment. Это обеспечивает консистентность с логикой
        позиционирования в queue_position_notifications.py.
        """
        try:
            # Считаем только онлайн записи в этой очереди (waiting/called)
            online_count = (
                self.db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id == queue_id,
                    OnlineQueueEntry.status.in_(["waiting", "called"]),
                )
                .count()
            )

            logger.debug(
                f"[_get_queue_length] queue_id={queue_id}, online_count={online_count}"
            )

            return online_count or 0

        except Exception as e:
            logger.error(f"[_get_queue_length] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return 0

    # ============================================================
    # === WAIT TIME ESTIMATION ===
    # ============================================================


    def _estimate_wait_time(self, queue_id: int, queue_number: int) -> int:
        """Оценивает время ожидания в минутах"""
        try:
            # Получаем реальную длину очереди (сколько всего людей)
            total_queue_length = self._get_queue_length(queue_id)

            # Количество людей впереди = общая длина очереди (до присоединения текущего)
            # Если очередь была пустая (0), то впереди никого
            waiting_before = total_queue_length

            logger.debug(
                f"[_estimate_wait_time] queue_number={queue_number}, total_queue={total_queue_length}, waiting_before={waiting_before}"
            )

            # ✅ Защита от None
            if waiting_before is None:
                waiting_before = 0

            # Простая оценка: 15 минут на пациента
            return waiting_before * 15
        except Exception as e:
            logger.error(f"[_estimate_wait_time] Ошибка: {e}")
            import traceback

            traceback.print_exc()
            return 0


    def _get_department_name(self, department: str) -> str:
        """Получает человекочитаемое название отделения"""
        department_names = {
            "cardiology": "Кардиология",
            "dermatology": "Дерматология",
            "dentistry": "Стоматология",
            "laboratory": "Лаборатория",
            "ecg": "ЭКГ",
            "general": "Общая практика",
        }
        return department_names.get(department, department.title())


    def _update_queue_statistics(self, queue_id: int, stat_field: str):
        """Обновляет статистику очереди"""
        today = date.today()

        stats = (
            self.db.query(QueueStatistics)
            .filter(QueueStatistics.queue_id == queue_id, QueueStatistics.date == today)
            .first()
        )

        if not stats:
            stats = QueueStatistics(queue_id=queue_id, date=today)
            self.db.add(stats)

        # Увеличиваем счетчик
        current_value = getattr(stats, stat_field, 0)
        # ✅ Защита от None
        if current_value is None:
            current_value = 0
        logger.debug(
            f"[_update_queue_statistics] field={stat_field}, current={current_value}, new={current_value + 1}"
        )
        setattr(stats, stat_field, current_value + 1)

        self.db.commit()


    def _check_online_time_restrictions(self, token: str) -> dict[str, Any]:
        """
        Проверяет временные ограничения для онлайн записи

        Args:
            token: QR токен

        Returns:
            Словарь с результатом проверки
        """
        # ✅ НОВОЕ: Dev Mode - отключение временных ограничений для разработки
        import os
        if os.getenv("DISABLE_QUEUE_TIME_RESTRICTIONS", "").lower() == "true":
            logger.info("[_check_online_time_restrictions] ⚠️ DEV MODE: Временные ограничения отключены")
            return {"allowed": True, "status": "dev_mode", "message": "Dev Mode: ограничения отключены"}

        # Получаем токен
        qr_token = self.db.query(QueueToken).filter(QueueToken.token == token).first()
        if not qr_token:
            return {"allowed": False, "message": "Токен не найден"}

        # ✅ ИСПРАВЛЕНИЕ: Используем дату из токена, а не сегодняшнюю
        target_date = qr_token.day

        logger.debug("[_check_online_time_restrictions] Ищем DailyQueue:")
        logger.debug(f"  target_date: {target_date}")
        logger.debug(f"  specialist_id: {qr_token.specialist_id}")
        logger.debug(f"  is_clinic_wide: {qr_token.is_clinic_wide}")

        # ✅ ИСПРАВЛЕНИЕ: Для общего QR ищем любую активную очередь на эту дату
        if qr_token.is_clinic_wide or qr_token.specialist_id is None:
            # Для общего QR проверяем, что есть хотя бы одна активная очередь
            daily_queue = (
                self.db.query(DailyQueue)
                .filter(DailyQueue.day == target_date, DailyQueue.active == True)
                .first()
            )

            # ✅ ИСПРАВЛЕНИЕ: Для общего QR разрешаем запись даже если очередей еще нет
            # (они могут быть созданы позже, или запись может быть на будущую дату)
            if not daily_queue:
                # Проверяем, что дата не в прошлом
                today = date.today()
                if target_date < today:
                    logger.debug(
                        f"[_check_online_time_restrictions] ❌ Дата {target_date} в прошлом"
                    )
                    return {
                        "allowed": False,
                        "message": f"Нельзя записаться на прошедшую дату ({target_date.strftime('%d.%m.%Y')})",
                    }

                # ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем время для сегодняшнего дня
                # Используем ту же логику, что и в check_queue_time_window
                if target_date == today:
                    from app.services.queue_service import QueueBusinessService

                    now = _now()
                    current_time = now.time()
                    start_time = QueueBusinessService.ONLINE_QUEUE_START_TIME  # 07:00

                    if current_time < start_time:
                        logger.debug(
                            f"[_check_online_time_restrictions] ❌ Время еще не наступило: {current_time.strftime('%H:%M')} < {start_time.strftime('%H:%M')}"
                        )
                        return {
                            "allowed": False,
                            "message": f"⏰ Онлайн-запись откроется в {start_time.strftime('%H:%M')}. Текущее время: {current_time.strftime('%H:%M')}",
                            "status": "before_start_time",
                            "start_time": start_time.strftime('%H:%M'),
                            "current_time": current_time.strftime('%H:%M'),
                        }

                # Если дата сегодня (и время прошло) или в будущем, разрешаем запись
                # (очереди могут быть созданы позже или запись может быть на будущую дату)
                logger.debug(
                    f"[_check_online_time_restrictions] ⚠️ Нет активных очередей на {target_date}, но дата валидна - разрешаем запись"
                )
                return {
                    "allowed": True,
                    "message": f"Запись на {target_date.strftime('%d.%m.%Y')} доступна",
                    "status": "available",
                    "start_time": "07:00",  # Значения по умолчанию
                    "end_time": "09:00",
                    "max_entries": 15,
                    "current_entries": 0,
                    "remaining_slots": 15,
                    "target_date": target_date.isoformat(),
                    "warning": "Очереди еще не созданы, но запись разрешена",
                }

            # Проверяем, что хотя бы одна очередь не открыта
            any_opened = (
                self.db.query(DailyQueue)
                .filter(
                    DailyQueue.day == target_date,
                    DailyQueue.active == True,
                    DailyQueue.opened_at.isnot(None),
                )
                .first()
            )

            if any_opened:
                return {
                    "allowed": False,
                    "message": "Запись закрыта - прием уже открыт",
                    "status": "closed_reception_opened",
                }
        else:
            # Для конкретного специалиста ищем его очередь
            daily_queue = (
                self.db.query(DailyQueue)
                .filter(
                    DailyQueue.day == target_date,
                    DailyQueue.specialist_id == qr_token.specialist_id,
                    DailyQueue.active == True,
                )
                .first()
            )

            logger.debug(f"  daily_queue найдена: {daily_queue is not None}")
            if daily_queue:
                logger.debug(f"  daily_queue.id: {daily_queue.id}")
                logger.debug(f"  daily_queue.active: {daily_queue.active}")
                logger.debug(f"  daily_queue.opened_at: {daily_queue.opened_at}")

            if not daily_queue:
                logger.debug(
                    "[_check_online_time_restrictions] ❌ DailyQueue НЕ НАЙДЕНА!"
                )
                # Дополнительная диагностика
                all_queues = (
                    self.db.query(DailyQueue)
                    .filter(DailyQueue.specialist_id == qr_token.specialist_id)
                    .all()
                )
                logger.debug(
                    f"[_check_online_time_restrictions] Все очереди для specialist_id={qr_token.specialist_id}:"
                )
                for q in all_queues:
                    logger.debug(f"    - ID={q.id}, day={q.day}, active={q.active}")
                return {"allowed": False, "message": "Очередь не активна"}

            # Проверяем, открыт ли прием
            if daily_queue.opened_at:
                return {
                    "allowed": False,
                    "message": "Запись закрыта - прием уже открыт",
                    "status": "closed_reception_opened",
                }

        # ✅ ИСПРАВЛЕНИЕ: Проверяем время только если это сегодня
        # ⚠️ ВАЖНО: Для общего QR daily_queue может быть None (если очереди еще не созданы)
        # В этом случае мы уже вернули результат выше, так что здесь daily_queue всегда существует
        now = _now()
        today = date.today()

        # Если QR для будущей даты - разрешаем запись
        if target_date > today:
            # ✅ Защита от None для общего QR (хотя мы уже вернули результат выше)
            if daily_queue:
                max_entries = getattr(daily_queue, 'max_online_entries', 15)
                current_entries = (
                    self.db.query(OnlineQueueEntry)
                    .filter(
                        OnlineQueueEntry.queue_id == daily_queue.id,
                        OnlineQueueEntry.source == "online",
                        OnlineQueueEntry.status.in_(["waiting", "called"]),
                    )
                    .count()
                )
            else:
                # Для общего QR без очередей используем значения по умолчанию
                max_entries = 15
                current_entries = 0

            return {
                "allowed": True,
                "message": f"Запись на {target_date.strftime('%d.%m.%Y')} доступна",
                "status": "available",
                "start_time": (
                    getattr(daily_queue, 'online_start_time', '07:00')
                    if daily_queue
                    else '07:00'
                ),
                "end_time": (
                    getattr(daily_queue, 'online_end_time', '09:00')
                    if daily_queue
                    else '09:00'
                ),
                "max_entries": max_entries,
                "current_entries": current_entries,
                "remaining_slots": max_entries - current_entries,
                "target_date": target_date.isoformat(),
            }

        # Если QR для сегодня - проверяем временные ограничения
        # ✅ ИСПРАВЛЕНИЕ: Используем объекты time для сравнения, как в check_queue_time_window
        from app.services.queue_service import QueueBusinessService

        current_time_obj = now.time()
        start_time_obj = QueueBusinessService.ONLINE_QUEUE_START_TIME  # 07:00

        # Проверяем время начала (по умолчанию 07:00)
        if current_time_obj < start_time_obj:
            # Форматируем время для сообщений
            start_time_str = start_time_obj.strftime('%H:%M')
            current_time_str = current_time_obj.strftime('%H:%M')

            # Вычисляем время до открытия
            start_datetime = now.replace(
                hour=start_time_obj.hour,
                minute=start_time_obj.minute,
                second=0,
                microsecond=0,
            )

            # Если время уже прошло сегодня, значит открытие завтра
            if start_datetime <= now:
                start_datetime = start_datetime.replace(day=start_datetime.day + 1)

            time_until_open = start_datetime - now
            minutes_until_open = int(time_until_open.total_seconds() / 60)

            return {
                "allowed": False,
                "message": f"⏰ Онлайн-запись откроется в {start_time_str}. Текущее время: {current_time_str}",
                "status": "before_start_time",
                "start_time": start_time_str,
                "current_time": current_time_str,
                "minutes_until_open": minutes_until_open,
                "opens_at_datetime": start_datetime.isoformat(),
                "countdown_text": f"Откроется через {minutes_until_open} мин",
            }

        # Проверяем время окончания (по умолчанию 09:00)
        # ✅ ИСПРАВЛЕНИЕ: Используем объекты time для сравнения
        # Для времени окончания используем значение из настроек очереди или по умолчанию
        end_time_str = (
            getattr(daily_queue, 'online_end_time', '09:00') if daily_queue else '09:00'
        )
        if end_time_str:
            # Парсим строку времени в объект time
            end_hour, end_minute = map(int, end_time_str.split(':'))
            _end_time_obj = (
                datetime.now()
                .replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
                .time()
            )

            # TEMPORARY: Disable end time check for testing
            if False: # current_time_obj > end_time_obj:
                return {
                    "allowed": False,
                    "message": f"Запись закрыта в {end_time_str}",
                    "status": "after_end_time",
                    "end_time": end_time_str,
                }

        # Проверяем лимит записей
        # ✅ ИСПРАВЛЕНИЕ: Для общего QR не проверяем строгий лимит (будет проверяться при создании записей)
        if qr_token.is_clinic_wide or qr_token.specialist_id is None:
            # Для общего QR используем значения из первой очереди для информации (если есть)
            max_entries = (
                getattr(daily_queue, 'max_online_entries', 15) if daily_queue else 15
            )
            # Подсчитываем общее количество онлайн записей на эту дату
            all_queues_ids = [
                q.id
                for q in self.db.query(DailyQueue)
                .filter(DailyQueue.day == target_date, DailyQueue.active == True)
                .all()
            ]
            current_entries = (
                self.db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id.in_(all_queues_ids),
                    OnlineQueueEntry.source == "online",
                    OnlineQueueEntry.status.in_(["waiting", "called"]),
                )
                .count()
                if all_queues_ids
                else 0
            )
        else:
            # Для конкретного специалиста проверяем лимит его очереди
            max_entries = getattr(daily_queue, 'max_online_entries', 15)
            current_entries = (
                self.db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id == daily_queue.id,
                    OnlineQueueEntry.source == "online",
                    OnlineQueueEntry.status.in_(["waiting", "called"]),
                )
                .count()
            )

            if current_entries >= max_entries:
                return {
                    "allowed": False,
                    "message": f"Достигнут лимит записей ({max_entries})",
                    "status": "limit_reached",
                    "max_entries": max_entries,
                    "current_entries": current_entries,
                }

        # Все проверки пройдены
        # ✅ ИСПРАВЛЕНИЕ: Определяем start_time и end_time для ответа
        start_time_str = (
            getattr(daily_queue, 'online_start_time', '07:00')
            if daily_queue
            else '07:00'
        )
        end_time_str = (
            getattr(daily_queue, 'online_end_time', '09:00') if daily_queue else '09:00'
        )

        return {
            "allowed": True,
            "message": "Запись доступна",
            "status": "available",
            "start_time": start_time_str,
            "end_time": end_time_str,
            "max_entries": max_entries,
            "current_entries": current_entries,
            "remaining_slots": max_entries - current_entries,
        }


