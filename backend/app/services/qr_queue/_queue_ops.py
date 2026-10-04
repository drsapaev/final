"""Queue_Ops mixin for QRQueueService.

Split from qr_queue_service.py.
"""

from __future__ import annotations

from datetime import date, datetime

from app.crud.clinic import clinic_today
from app.crud.daily_queue_creation_policy import (
    OnlineAdmissionWindow,
    evaluate_online_admission_window,
    online_admission_window,
)
from app.crud.queue_resource_routing import (
    find_inactive_daily_queue_for_specialist,
    prefer_registry_surface,
    resolve_registry_tag_queue_for_specialist,
    resolve_tag_resource,
)
from app.models.clinic import Doctor
from app.services.qr_queue._base import *  # noqa: F401, F403
from app.services.qr_queue._base import QRQueueServiceMixinBase, _now


def _before_start_wait_fields(
    target_date: date,
    now: datetime,
    window: OnlineAdmissionWindow,
) -> dict[str, str | int]:
    """Preserve the QR client's countdown contract for a closed start window."""
    opens_at = datetime.combine(target_date, window.start_time, tzinfo=now.tzinfo)
    seconds_until_open = max(0, int((opens_at - now).total_seconds()))
    minutes_until_open = max(1, (seconds_until_open + 59) // 60)
    return {
        "minutes_until_open": minutes_until_open,
        "opens_at_datetime": opens_at.isoformat(),
        "countdown_text": f"Откроется через {minutes_until_open} мин",
    }


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
            # Codex round-25 P2: день — по SSOT клиники (таймзона настроек
            # очередей): host date.today() на UTC-хосте между 19:00 и
            # полуночью уже «вчера» для Asia/Tashkent — живая очередь
            # (штампованная следующим ЛОКАЛЬНЫМ днём) не находилась, и
            # /queue/status/{specialist_id} отвечал «не активна» при
            # ждущих пациентах.
            target_date = clinic_today(self.db)

        daily_queue = (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.day == target_date, DailyQueue.specialist_id == specialist_id
            )
            .first()
        )

        # QD-2C (Codex round-2 P2): очередь тега реестра может быть
        # resource-owned (specialist NULL) — тот же fallback, что и
        # call_next_patient, иначе статус «не активна» при живой очереди
        # (и вызываемом тем же specialist_id пациенте).
        # Codex round-5 P1: НЕАКТИВНАЯ легаси-строка не затеняет живую
        # ресурсную поверхность (lookup без active-предиката).
        daily_queue = prefer_registry_surface(
            self.db, daily_queue, target_date, specialist_id
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
        queue_tag: str | None = None,
    ) -> dict[str, Any]:
        """
        Вызывает следующего пациента в очереди

        Args:
            specialist_id: ID специалиста
            called_by_user_id: ID пользователя, вызвавшего пациента
            target_date: Дата очереди (по умолчанию сегодня)
            queue_tag: Опциональный тег очереди (GQL-AUDIT-28 follow-up):
                когда задан, вызов происходит из очереди этого тега, а не
                из произвольной активной очереди специалиста

        Returns:
            Информация о вызванном пациенте
        """
        # Codex round-25 P2: дефолт опущенной даты — день КЛИНИКИ по SSOT
        # (таймзона настроек очередей), как в GQL/quick-call путях: иначе
        # тот же ранний-вечернийUTC-хост искал вчерашнюю очередь и
        # «Очередь не активна» при живом ресурсном пациенте.
        queue_date = target_date if target_date else clinic_today(self.db)
        queue_query = self.db.query(DailyQueue).filter(
            DailyQueue.day == queue_date,
            DailyQueue.specialist_id == specialist_id,
            DailyQueue.active == True,
        )
        if queue_tag:
            queue_query = queue_query.filter(DailyQueue.queue_tag == queue_tag)
        candidate_queues = queue_query.all()

        # QD-2C (Codex round-1 P1): очередь тега реестра может быть
        # resource-owned (specialist NULL — утренний пре-креат или любой
        # пост-свитч писатель), и doctor-keyed-поиск её не видит: "очередь
        # не активна", waiting-пациенты не продвигаются канонической
        # командой. Legacy-идентичность (synthetic Doctor id / явный тег)
        # по-прежнему именует тег: резолвим (day, tag)-поверхность, когда
        # тег имеет строку реестра; doctor-теги сохраняют контракт PR-26.
        if not candidate_queues:
            tag_queue = resolve_registry_tag_queue_for_specialist(
                self.db, queue_date, specialist_id, queue_tag
            )
            if tag_queue is not None:
                candidate_queues = [tag_queue]

        # Codex P1 (round-14): поверхность реестра предпочитается ДО
        # принятия doctor-keyed кандидатов — fallback выше срабатывал
        # только на ПУСТОМ списке. На upgraded-клинике рядом с живой
        # resource-очередью может остаться АКТИВНЫЙ untagged
        # synthetic-shadow (легаси-писатели ещё смонтированы, round-6):
        # выбор уходил shadow'у → «нет пациентов», пока пациенты ждут
        # на поверхности. Поверхность возглавляет кандидатов; untagged
        # строки (не на оси тега) выпадают; tagged doctor-строки
        # (мост 0059) остаются сканируемыми. Doctor-теги без поверхности
        # (surface is None) не тронуты — байт-идентично.
        if candidate_queues:
            surface = resolve_registry_tag_queue_for_specialist(
                self.db, queue_date, specialist_id, queue_tag
            )
            if surface is not None:
                surface_ids = {surface.id}
                candidate_queues = [
                    q
                    for q in candidate_queues
                    if q.queue_tag is not None or q.id in surface_ids
                ]
                if surface.id not in {q.id for q in candidate_queues}:
                    candidate_queues = [surface] + candidate_queues

        # Codex P1 (round-12): без queue_tag у врача с несколькими активными
        # tagged-очередями неупорядоченный .first() выбирал произвольную —
        # «нет пациентов» при waiting в соседней очереди / вызов не из того
        # workflow. Детерминированный выбор: очередь с самым ранним waiting-
        # кандидатом; при одиночной очереди поведение прежнее.
        #
        # Codex P1 (round-13): номера локальны для каждой очереди, поэтому
        # «минимальный number» НЕ означает «самое раннее прибытие» (пациент
        # #5, ждущий час, проигрывал свежему #1 соседней очереди). Канонический
        # порядок вызова — как в queue_svc/_helpers.py staff_call_next_patient:
        # priority DESC, coalesce(queue_time, created_at) ASC, id ASC.
        if not candidate_queues:
            raise ValueError(f"Очередь не активна на дату {queue_date}")
        if len(candidate_queues) == 1:
            daily_queue = candidate_queues[0]
        else:
            # Codex P1 (round-14): скан лочит ВЫИГРАВШУЮ запись — при двух
            # параллельных вызовах без тега второй ждёт на этом SELECT FOR
            # UPDATE, после коммита первого его предикат (waiting)
            # переоценивается и он берёт следующий канонический кандидат,
            # а не «следующего из уже выбранной очереди».
            earliest = (
                self.db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id.in_([q.id for q in candidate_queues]),
                    OnlineQueueEntry.status == "waiting",
                )
                .order_by(
                    OnlineQueueEntry.priority.desc(),
                    func.coalesce(
                        OnlineQueueEntry.queue_time,
                        OnlineQueueEntry.created_at,
                    ).asc(),
                    OnlineQueueEntry.id.asc(),
                )
                .with_for_update()
                .first()
            )
            if earliest is not None:
                daily_queue = next(
                    q for q in candidate_queues if q.id == earliest.queue_id
                )
            else:
                # waiting нигде нет — детерминированный ответ "нет пациентов"
                daily_queue = min(candidate_queues, key=lambda q: q.id)

        if not daily_queue:
            raise ValueError(f"Очередь не активна на дату {queue_date}")

        # Находим следующего пациента в статусе "waiting" — тот же
        # канонический порядок (round-13), что и при выборе очереди выше:
        # вызван должен быть именно канонически самый ранний кандидат.
        # QUEUE-AUDIT-28 P0-7: with_for_update() — защита от race condition.
        # Раньше два врача могли одновременно вызвать одного пациента.
        next_patient = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.status == "waiting",
            )
            .order_by(
                OnlineQueueEntry.priority.desc(),
                func.coalesce(
                    OnlineQueueEntry.queue_time,
                    OnlineQueueEntry.created_at,
                ).asc(),
                OnlineQueueEntry.id.asc(),
            )
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
        # Codex round-38 P2: штамп статистики — КЛИНИК-локальный день
        # (clinic_today SSOT, таймзона настроек очередей): host
        # date.today() на UTC-хосте между 19:00 и полуночью уже
        # «вчера» для Asia/Tashkent — QR-join записывался под прошлым
        # днём и выпадал из /admin/queue-analytics даже при явном
        # запросе актуального клиник-дня.
        today = clinic_today(self.db)

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
            logger.info(
                "[_check_online_time_restrictions] ⚠️ DEV MODE: Временные ограничения отключены"
            )
            return {
                "allowed": True,
                "status": "dev_mode",
                "message": "Dev Mode: ограничения отключены",
            }

        # Получаем токен
        qr_token = self.db.query(QueueToken).filter(QueueToken.token == token).first()
        if not qr_token:
            return {"allowed": False, "message": "Токен не найден"}

        # ✅ ИСПРАВЛЕНИЕ: Используем дату из токена, а не сегодняшнюю
        target_date = qr_token.day

        # Codex round-30 P2: и день QR-сессии, и текущее время — в
        # таймзоне КЛИНИКИ (настройки очередей): resource-очереди
        # создаются на КЛИНИК-локальном дне, и host date.today() в окне
        # 19:00-24:00Z классифицировал текущий клиник-день как «будущий
        # QR» — запись разрешалась до 07:00 клиник-времени, минуя окно
        # старта онлайн-записи. Одни и те же now/today используются
        # обеими ветками (общий и specialist QR); _now() сохраняет
        # тестовую заморозку времени.
        from zoneinfo import ZoneInfo

        from app.crud.clinic import get_queue_settings

        queue_settings = get_queue_settings(self.db)
        _tz_name = queue_settings.get("timezone", "Asia/Tashkent")
        now = _now(ZoneInfo(_tz_name))
        today = now.date()

        logger.debug("[_check_online_time_restrictions] Ищем DailyQueue:")
        logger.debug(f"  target_date: {target_date}")
        logger.debug(f"  specialist_id: {qr_token.specialist_id}")
        logger.debug(f"  is_clinic_wide: {qr_token.is_clinic_wide}")

        # ✅ ИСПРАВЛЕНИЕ: Для общего QR ищем любую активную очередь на эту дату
        if qr_token.is_clinic_wide or qr_token.specialist_id is None:
            # Для общего QR проверяем, что есть хотя бы одна активная очередь
            daily_queues = (
                self.db.query(DailyQueue)
                .filter(DailyQueue.day == target_date, DailyQueue.active == True)
                .order_by(DailyQueue.id.asc())
                .all()
            )

            # ✅ ИСПРАВЛЕНИЕ: Для общего QR разрешаем запись даже если очередей еще нет
            # (они могут быть созданы позже, или запись может быть на будущую дату)
            if not daily_queues:
                # Проверяем, что дата не в прошлом (clinic-day SSOT)
                if target_date < today:
                    logger.debug(
                        f"[_check_online_time_restrictions] ❌ Дата {target_date} в прошлом"
                    )
                    return {
                        "allowed": False,
                        "message": f"Нельзя записаться на прошедшую дату ({target_date.strftime('%d.%m.%Y')})",
                    }

                window = online_admission_window(
                    daily_queue=None,
                    settings=queue_settings,
                )
                window_fields = {
                    "policy_version": window.policy_version,
                    "start_time": window.start_time.strftime("%H:%M"),
                    "end_time": (
                        window.end_time.strftime("%H:%M")
                        if window.end_time is not None
                        else None
                    ),
                    "target_date": target_date.isoformat(),
                    "queue_length": 0,
                }
                window_result = evaluate_online_admission_window(
                    target_date, now, window
                )
                if window_result == "before_start":
                    return {
                        "allowed": False,
                        "message": (
                            "Онлайн-запись откроется в "
                            f"{window_fields['start_time']}"
                        ),
                        "status": "before_start_time",
                        "current_time": now.strftime("%H:%M"),
                        **window_fields,
                        **_before_start_wait_fields(target_date, now, window),
                    }
                if window_result == "after_end":
                    return {
                        "allowed": False,
                        "message": (
                            "Онлайн-запись закрыта в " f"{window_fields['end_time']}"
                        ),
                        "status": "after_end_time",
                        **window_fields,
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
                    **window_fields,
                    "max_entries": None,
                    "current_entries": 0,
                    "max_online_entries": None,
                    "online_issued_count": None,
                    "online_bookings_remaining": None,
                    "remaining_slots": None,
                    "target_date": target_date.isoformat(),
                    "warning": "Очереди еще не созданы, но запись разрешена",
                }

            overview_queue_ids = [queue.id for queue in daily_queues]
            overview_queue_length = (
                self.db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id.in_(overview_queue_ids),
                    OnlineQueueEntry.status.in_(["waiting", "called"]),
                )
                .count()
                if overview_queue_ids
                else 0
            )

            # A clinic-wide QR is an overview before the patient selects a
            # concrete owner. Never let the first DailyQueue row impose its
            # legacy/v1 window on every other destination in a mixed day.
            # The selected queue is checked again by the canonical join.
            available_queues = []
            before_start_queues = []
            after_end_queues = []
            opened_queues = []
            for queue in daily_queues:
                # Opening one direction closes admission only for that
                # queue. Other directions may have a later frozen v1 window
                # and remain selectable through the clinic-wide overview.
                if queue.opened_at is not None:
                    opened_queues.append(queue)
                    continue
                queue_window = online_admission_window(
                    daily_queue=queue,
                    settings=queue_settings,
                )
                result = evaluate_online_admission_window(
                    target_date, now, queue_window
                )
                if result == "available":
                    available_queues.append((queue, queue_window))
                elif result == "before_start":
                    before_start_queues.append((queue, queue_window))
                elif result == "after_end":
                    after_end_queues.append((queue, queue_window))

            if available_queues:
                daily_queue, _ = available_queues[0]
            elif before_start_queues:
                _, window = min(
                    before_start_queues,
                    key=lambda item: item[1].start_time,
                )
                window_fields = {
                    "policy_version": window.policy_version,
                    "start_time": window.start_time.strftime("%H:%M"),
                    "end_time": (
                        window.end_time.strftime("%H:%M")
                        if window.end_time is not None
                        else None
                    ),
                    "target_date": target_date.isoformat(),
                    "queue_length": overview_queue_length,
                }
                return {
                    "allowed": False,
                    "message": (
                        "Онлайн-запись откроется в " f"{window_fields['start_time']}"
                    ),
                    "status": "before_start_time",
                    "current_time": now.strftime("%H:%M"),
                    **window_fields,
                    **_before_start_wait_fields(target_date, now, window),
                }
            elif after_end_queues:
                _, window = max(
                    after_end_queues,
                    key=lambda item: item[1].end_time,
                )
                window_fields = {
                    "policy_version": window.policy_version,
                    "start_time": window.start_time.strftime("%H:%M"),
                    "end_time": (
                        window.end_time.strftime("%H:%M")
                        if window.end_time is not None
                        else None
                    ),
                    "target_date": target_date.isoformat(),
                    "queue_length": overview_queue_length,
                }
                return {
                    "allowed": False,
                    "message": (
                        "Онлайн-запись закрыта в " f"{window_fields['end_time']}"
                    ),
                    "status": "after_end_time",
                    **window_fields,
                }
            elif opened_queues:
                return {
                    "allowed": False,
                    "message": "Запись закрыта - прием уже открыт",
                    "status": "closed_reception_opened",
                    "queue_length": overview_queue_length,
                }
            else:
                return {
                    "allowed": False,
                    "message": f"Нельзя записаться на прошедшую дату ({target_date:%d.%m.%Y})",
                    "status": "date_past",
                    "target_date": target_date.isoformat(),
                    "queue_length": overview_queue_length,
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
            # QD-2C (Codex round-2 P1): resource-owned очередь тега реестра
            # видна через fallback реестра — не только doctor-keyed lookup.
            # Codex P2 (round-14): PREFER, а не только empty-fallback —
            # активный doctor-keyed shadow (opened_at/capacity/window
            # расходятся с поверхностью) не должен затенять живую
            # поверхность в QR-проверках: скан QR может отклонить живую
            # очередь или открыть сессию, которую аллокация затем
            # отклонит. Врач-теги без поверхности не тронуты.
            daily_queue = prefer_registry_surface(
                self.db, daily_queue, target_date, qr_token.specialist_id
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
                doctor = (
                    self.db.query(Doctor)
                    .filter(Doctor.id == qr_token.specialist_id)
                    .first()
                )
                resource = (
                    resolve_tag_resource(self.db, doctor.specialty)
                    if doctor is not None and doctor.specialty
                    else None
                )
                inactive_identity = find_inactive_daily_queue_for_specialist(
                    self.db,
                    target_date,
                    qr_token.specialist_id,
                    doctor.specialty if doctor is not None else None,
                )
                if inactive_identity is not None:
                    # The identity guard prevents a replacement queue from
                    # resetting this persisted counter. Do not report current
                    # defaults as a fresh quota for that inactive identity.
                    return {
                        "allowed": False,
                        "message": "Очередь не активна",
                        "status": "queue_inactive",
                        "target_date": target_date.isoformat(),
                        "queue_length": 0,
                        "policy_version": None,
                        "max_online_entries": None,
                        "online_issued_count": None,
                        "online_bookings_remaining": None,
                    }
                owner_default = (
                    resource.max_online_per_day
                    if resource is not None
                    else getattr(doctor, "max_online_per_day", None)
                )
                max_online_entries = 15 if owner_default is None else owner_default
                window = online_admission_window(
                    daily_queue=None,
                    settings=queue_settings,
                )
                is_v1 = window.policy_version == "daily_online_issuances_v1"
                return {
                    "allowed": False,
                    "message": "Очередь не активна",
                    "status": "queue_inactive",
                    "policy_version": window.policy_version,
                    "start_time": window.start_time.strftime("%H:%M"),
                    "end_time": (
                        window.end_time.strftime("%H:%M")
                        if window.end_time is not None
                        else None
                    ),
                    "queue_length": 0,
                    "max_online_entries": max_online_entries,
                    "online_issued_count": 0 if is_v1 else None,
                    "online_bookings_remaining": (
                        max(0, max_online_entries) if is_v1 else None
                    ),
                    "max_entries": max_online_entries,
                    "current_entries": 0,
                    "remaining_slots": max_online_entries,
                }

            queue_length = (
                self.db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id == daily_queue.id,
                    OnlineQueueEntry.status.in_(["waiting", "called"]),
                )
                .count()
            )
            current_entries = (
                self.db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id == daily_queue.id,
                    OnlineQueueEntry.source == "online",
                    OnlineQueueEntry.status.in_(["waiting", "called"]),
                )
                .count()
            )
            policy_version = getattr(daily_queue, "policy_version", "legacy")
            max_online_entries = daily_queue.max_online_entries
            if policy_version == "daily_online_issuances_v1":
                online_issued_count = daily_queue.online_issued_count
                online_bookings_remaining = max(
                    0, max_online_entries - online_issued_count
                )
            else:
                online_issued_count = None
                online_bookings_remaining = None
                # Preserve the established legacy admission fallback.
                max_online_entries = max_online_entries or 15
            concrete_quota_fields = {
                "queue_length": queue_length,
                "policy_version": policy_version,
                "max_online_entries": max_online_entries,
                "online_issued_count": online_issued_count,
                "online_bookings_remaining": online_bookings_remaining,
                "current_entries": current_entries,
                "remaining_slots": max_online_entries - current_entries,
            }

            # Проверяем, открыт ли прием
            if daily_queue.opened_at:
                return {
                    "allowed": False,
                    "message": "Запись закрыта - прием уже открыт",
                    "status": "closed_reception_opened",
                    **concrete_quota_fields,
                }

        window = online_admission_window(
            daily_queue=daily_queue,
            settings=queue_settings,
        )
        window_fields = {
            "policy_version": window.policy_version,
            "start_time": window.start_time.strftime("%H:%M"),
            "end_time": (
                window.end_time.strftime("%H:%M")
                if window.end_time is not None
                else None
            ),
            "target_date": target_date.isoformat(),
        }
        is_clinic_wide = qr_token.is_clinic_wide or qr_token.specialist_id is None
        if is_clinic_wide:
            window_fields.update(
                {
                    "queue_length": overview_queue_length,
                    "max_online_entries": None,
                    "online_issued_count": None,
                    "online_bookings_remaining": None,
                }
            )
        else:
            window_fields.update(concrete_quota_fields)

        # Future dates retain the current contract: the same-day clock
        # boundaries do not reject a future booking.
        if target_date > today:
            if is_clinic_wide:
                return {
                    "allowed": True,
                    "message": f"Запись на {target_date.strftime('%d.%m.%Y')} доступна",
                    "status": "available",
                    **window_fields,
                    "max_online_entries": None,
                    "online_issued_count": None,
                    "online_bookings_remaining": None,
                    "max_entries": None,
                    "current_entries": None,
                    "remaining_slots": None,
                }

            max_entries = max_online_entries

            return {
                # Future-date availability has historically been advisory.
                # Keep it available here while still exposing saved quota
                # facts; the final admission path owns enforcement.
                "allowed": True,
                "message": f"Запись на {target_date.strftime('%d.%m.%Y')} доступна",
                "status": "available",
                **window_fields,
                "max_online_entries": max_entries,
                "online_issued_count": online_issued_count,
                "online_bookings_remaining": online_bookings_remaining,
                "remaining_slots": concrete_quota_fields["remaining_slots"],
                "max_entries": max_entries,
                "current_entries": current_entries,
            }

        window_result = evaluate_online_admission_window(target_date, now, window)
        if window_result == "date_past":
            return {
                "allowed": False,
                "message": f"Нельзя записаться на прошедшую дату ({target_date:%d.%m.%Y})",
                "status": "date_past",
                **window_fields,
            }
        if window_result == "before_start":
            return {
                "allowed": False,
                "message": f"Онлайн-запись откроется в {window_fields['start_time']}",
                "status": "before_start_time",
                "current_time": now.strftime("%H:%M"),
                **window_fields,
                **_before_start_wait_fields(target_date, now, window),
            }
        if window_result == "after_end":
            return {
                "allowed": False,
                "message": f"Онлайн-запись закрыта в {window_fields['end_time']}",
                "status": "after_end_time",
                **window_fields,
            }

        # Проверяем лимит записей
        # ✅ ИСПРАВЛЕНИЕ: Для общего QR не проверяем строгий лимит (будет проверяться при создании записей)
        if is_clinic_wide:
            # A clinic-wide overview can contain different owners and policy
            # versions; it has a queue length but no single queue quota.
            # Подсчитываем общее количество онлайн записей на эту дату
            all_queues_ids = overview_queue_ids
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
            queue_length = overview_queue_length
            max_entries = None
            online_issued_count = None
            online_bookings_remaining = None
        else:
            max_entries = max_online_entries
            online_issued_count = concrete_quota_fields["online_issued_count"]
            online_bookings_remaining = concrete_quota_fields[
                "online_bookings_remaining"
            ]
            quota_reached = (
                online_issued_count >= max_entries
                if policy_version == "daily_online_issuances_v1"
                else current_entries >= max_entries
            )

            if quota_reached:
                return {
                    "allowed": False,
                    "message": f"Достигнут лимит записей ({max_entries})",
                    "status": "limit_reached",
                    "max_entries": max_entries,
                    "current_entries": current_entries,
                    "max_online_entries": max_entries,
                    "online_issued_count": online_issued_count,
                    "online_bookings_remaining": online_bookings_remaining,
                    "remaining_slots": concrete_quota_fields["remaining_slots"],
                    **window_fields,
                }

        return {
            "allowed": True,
            "message": "Запись доступна",
            "status": "available",
            **window_fields,
            "max_entries": max_entries,
            "current_entries": current_entries,
            "max_online_entries": max_entries,
            "online_issued_count": online_issued_count,
            "online_bookings_remaining": online_bookings_remaining,
            "remaining_slots": (
                None if is_clinic_wide else concrete_quota_fields["remaining_slots"]
            ),
        }
