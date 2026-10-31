"""
Сервис для массового переноса очереди на завтра (форс-мажор)
согласно ONLINE_QUEUE_SYSTEM_V2.md раздел 20.3

Используется когда:
- Смена врача закончилась, но в очереди остались люди
- Врачу срочно нужно уйти (болезнь, экстренная ситуация)
- Форс-мажорные обстоятельства в клинике
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final

from sqlalchemy import func, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud.clinic import clinic_today
from app.crud.daily_queue_creation_policy import daily_queue_creation_snapshot
from app.crud.queue_resource_routing import (
    lock_daily_queue_creation,
    resolve_registry_tag_queue_for_specialist,
    resolve_tag_resource,
    tag_routes_to_resource,
)
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.payment import Payment
from app.models.refund_deposit import (
    DepositTransaction,
    DepositTransactionType,
    PatientDeposit,
    PaymentRefundClaim,
    RefundRequest,
    RefundRequestStatus,
    RefundType,
)
from app.models.visit import Visit
from app.repositories.queue_api_repository import QueueApiRepository
from app.services.fcm_service import get_fcm_service
from app.services.queue_service import queue_service

logger = logging.getLogger(__name__)


# 3808 review round 8 (P1 queue tag): sentinel «тег источника НЕ передан».
# Отличается от None: явный None — валидированный источник БЕЗ тега (сохрани
# NULL-тег назначения), sentinel — legacy-вызов, у которого тег выводится из
# Doctor.specialty (байт-идентичное прежнее поведение до этого раунда).
_SOURCE_TAG_UNSET: Final[object] = object()


class ForceMajeureError(Exception):
    """Ошибка при обработке форс-мажора"""

    pass


class ForceMajeureService:
    """
    Сервис для обработки форс-мажорных ситуаций с очередью

    Основные функции:
    1. Массовый перенос записей на завтра (первыми в очереди)
    2. Массовая отмена с возвратом средств
    3. Уведомление пациентов о переносе/отмене
    """

    TRANSFER_PRIORITY = 2  # Приоритет для перенесённых записей (выше обычного)

    def __init__(self, db: Session):
        self.db = db
        self.fcm_service = get_fcm_service()

    def get_pending_entries(
        self,
        queue_id: int | None = None,
        specialist_id: int | None = None,
        target_date: date | None = None,
    ) -> list[OnlineQueueEntry]:
        """
        Получить записи в ожидании для переноса/отмены

        Args:
            queue_id: ID конкретной очереди
            specialist_id: ID специалиста
            target_date: Дата (по умолчанию сегодня)

        Returns:
            Список записей со статусами waiting, called, in_service, diagnostics
        """
        # Codex round-26 P2: опущенная дата — день КЛИНИКИ по SSOT
        # (clinic_today, таймзона настроек очередей): mounted
        # ForceMajeureModal опускает target_date, и host date.today()
        # на UTC-хосте между 19:00 и 24:00 искал ВЧЕРАШНИЙ день клиники
        # — ресурсная поверхность не находилась, fallback на
        # specialist_id не матчит pure-resource очередь (specialist NULL).
        target_date = target_date or clinic_today(self.db)

        query = self.db.query(OnlineQueueEntry).join(DailyQueue)

        if queue_id:
            query = query.filter(OnlineQueueEntry.queue_id == queue_id)

        if specialist_id:
            # QD-2C (Codex round-6 P1): resource-owned queues of a
            # registry tag are invisible to the specialist filter
            # (specialist NULL) — Admin/Registrar address the tag
            # SURFACE of the specialist, not the doctor owner.
            surface = resolve_registry_tag_queue_for_specialist(
                self.db, target_date, specialist_id, None
            )
            if surface is not None:
                query = query.filter(OnlineQueueEntry.queue_id == surface.id)
            else:
                query = query.filter(DailyQueue.specialist_id == specialist_id)

        query = query.filter(
            DailyQueue.day == target_date,
            OnlineQueueEntry.status.in_(["waiting", "called"]),
        )

        return query.order_by(
            OnlineQueueEntry.priority.desc(), OnlineQueueEntry.queue_time
        ).all()

    _PENDING_STATUSES = ("waiting", "called")

    # 3808 review round 4 (P1 cross-channel): каналы единого refund-guard
    # (payment_refund_claims, миграция 0088) — значения закреплены и в
    # backfill этой миграции.
    REFUND_CHANNEL_DEPOSIT = "deposit"
    REFUND_CHANNEL_REFUND_REQUEST = "refund_request"

    # 3808 review round 5 (P1 claim lifecycle): статусы банковской заявки,
    # при которых возврат считается живым — состоявшимся или в выплате.
    # Только они удерживают единый claim платежа и входят в предикаты
    # 0087/0088 (status IN ...).
    REFUND_REQUEST_ACTIVE_STATUSES = (
        "pending",
        "approved",
        "processing",
        "completed",
    )
    # Терминальные не-платящие статусы: заявка НЕ вернула деньги — claim
    # освобождается (reject в process_refund_request + ленивое
    # самоисцеление в _claim_payment_refund), платёж снова доступен для
    # возврата любым каналом, включая исправленную повторную заявку.
    REFUND_REQUEST_FAILED_STATUSES = ("rejected", "cancelled")

    def transfer_entries_to_tomorrow(
        self,
        entries: list[OnlineQueueEntry],
        specialist_id: int,
        reason: str,
        performed_by_id: int,
        send_notifications: bool = True,
        source_date: date | None = None,
        source_queue: DailyQueue | None = None,
    ) -> dict[str, Any]:
        """
        Массовый перенос записей на завтра

        Записи получают высокий приоритет (2) и будут первыми в очереди
        после утреннего распределения.

        Args:
            entries: Список записей для переноса
            specialist_id: ID специалиста
            reason: Причина переноса
            performed_by_id: ID пользователя, выполнившего перенос
            send_notifications: Отправить уведомления
            source_date: День очереди-источника (по умолчанию — день
                клиники). «Завтра» считается от НЕГО: перенос будущей
                очереди (например, 5 ноября) ведёт на 6 ноября, а не на
                «завтра от сегодня» (3808 review round 2 P1 — раньше
                записи будущей очереди пересоздавались задним числом).
            source_queue: Каноническая очередь-источник (валидированная
                строка из API-слоя, контракт daily_queue_id). Без неё
                поверхность выводится из очередей самих записей.

        Returns:
            Результат операции с деталями
        """
        if not entries:
            return {
                "success": True,
                "transferred": 0,
                "message": "Нет записей для переноса",
            }

        # Codex round-26 P2: «завтра» — от дня КЛИНИКИ (тот же SSOT,
        # что и резолв записей выше): host-завтра в раннем-вечернем
        # окне = СЕГОДНЯ клиники — перенос сваливался бы в исходный
        # день, из которого записи пришли.
        # 3808 review round 2 (P1): день-источник передаёт вызывающий
        # слой (target_date запроса); дефолт — день клиники для
        # прямых вызовов сервиса (совместимость с текущими тестами).
        base_day = source_date or clinic_today(self.db)
        tomorrow = base_day + timedelta(days=1)

        # Получаем или создаём очередь на завтра.
        # 3808 review round 7 (P1 destination owner): поверхность
        # назначения сохраняет владельца ИСТОЧНИКА. Врачебная
        # каноническая строка (контракт daily_queue_id) переносится
        # ТОЛЬКО во врачебную очередь следующего дня — никогда в
        # общий ресурсный surface того же тега; ресурсный источник
        # остаётся на реестровой поверхности своего тега. Смена
        # владельца — явная операция, не побочный эффект форс-мажора.
        effective_source = source_queue or self._entries_source_queue(
            entries, specialist_id
        )
        tomorrow_queue = self._destination_queue(
            effective_source, specialist_id, tomorrow
        )

        transferred = []
        failed = []
        # 3808 review round 3 (P1 re-check under lock): entries processed
        # by a concurrent writer after our selection are skipped, never
        # transferred a second time.
        skipped = []
        notification_targets = []

        # R19 P2 (E-039 snapshot integration, #3279): единый SSOT-счётчик
        # живых писателей (QR join, ресепшн, batch, visit confirmation):
        # снимок дня (DailyQueue.start_number, 0067) СТАРШЕ живого
        # реестра; FOR UPDATE-блокировка сериализует с параллельной
        # регистрацией (RQ-14.a). Прежний локальный MAX+1 игнорировал
        # снимок (врачебная очередь: первый перенесённый — №1 при
        # старте дня 41), а отдельный resource_floor читал ЖИВОЕ
        # QueueResource.start_number_online ПОВЕРХ снимка (изменение
        # настройки 41 -> 501 уводило перенесённых из заморожённой
        # последовательности, которую обычная регистрация соблюдает).
        next_number = queue_service.get_next_queue_number(
            self.db,
            daily_queue=tomorrow_queue,
            queue_tag=tomorrow_queue.queue_tag,
        )

        for entry in entries:
            try:
                # 3808 review round 3 (P1 re-check): fresh statement per
                # entry — READ COMMITTED re-read; an entry whose status was
                # changed by a concurrent writer after selection is not
                # transferred (and its payment is never touched twice).
                self.db.refresh(entry)
                if entry.status not in self._PENDING_STATUSES:
                    skipped.append(
                        {"entry_id": entry.id, "status": entry.status}
                    )
                    continue

                # Создаём новую запись на завтра
                new_entry = OnlineQueueEntry(
                    queue_id=tomorrow_queue.id,
                    number=next_number,
                    patient_id=entry.patient_id,
                    patient_name=entry.patient_name,
                    phone=entry.phone,
                    telegram_id=entry.telegram_id,
                    birth_year=entry.birth_year,
                    address=entry.address,
                    visit_id=entry.visit_id,
                    visit_type=entry.visit_type,
                    discount_mode=entry.discount_mode,
                    services=entry.services,
                    service_codes=entry.service_codes,
                    total_amount=entry.total_amount,
                    source="force_majeure_transfer",
                    status="waiting",
                    priority=self.TRANSFER_PRIORITY,  # Высокий приоритет
                    queue_time=datetime.now(UTC),  # Новое время в очереди
                )

                self.db.add(new_entry)

                # Отмечаем старую запись как перенесённую
                entry.status = "cancelled"
                entry.incomplete_reason = f"Форс-мажор: {reason}"

                transferred.append(
                    {
                        "old_entry_id": entry.id,
                        "new_entry_id": None,  # Будет заполнено после flush
                        "patient_name": entry.patient_name,
                        "phone": entry.phone,
                        "telegram_id": entry.telegram_id,
                        "new_number": next_number,
                        "new_date": str(tomorrow),
                    }
                )

                # Добавляем в список для уведомлений
                if entry.phone or entry.telegram_id:
                    notification_targets.append(
                        {
                            "phone": entry.phone,
                            "telegram_id": entry.telegram_id,
                            "patient_name": entry.patient_name,
                            "new_number": next_number,
                            "new_date": tomorrow,
                        }
                    )

                next_number += 1

            except Exception as e:
                logger.error(f"Ошибка при переносе записи {entry.id}: {e}")
                failed.append({"entry_id": entry.id, "error": str(e)})

        self.db.flush()

        # Обновляем ID новых записей
        for _i, _item in enumerate(transferred):
            # ID будут присвоены после flush
            pass

        self.db.commit()

        # Отправляем уведомления
        if send_notifications and notification_targets:
            self._send_transfer_notifications(notification_targets, reason)

        logger.info(
            f"Форс-мажор перенос: {len(transferred)} записей перенесено на {tomorrow}, "
            f"{len(failed)} ошибок, {len(skipped)} пропущено. Причина: {reason}"
        )

        return {
            "success": True,
            "transferred": len(transferred),
            "failed": len(failed),
            "skipped": len(skipped),
            "new_date": str(tomorrow),
            "new_queue_id": tomorrow_queue.id,
            "details": transferred,
            "errors": failed,
            "skipped_details": skipped,
            "reason": reason,
        }

    def cancel_entries_with_refund(
        self,
        entries: list[OnlineQueueEntry],
        reason: str,
        refund_type: RefundType,
        performed_by_id: int,
        send_notifications: bool = True,
    ) -> dict[str, Any]:
        """
        Массовая отмена записей с возвратом средств

        Args:
            entries: Список записей для отмены
            reason: Причина отмены
            refund_type: Тип возврата (депозит или ручной возврат)
            performed_by_id: ID пользователя, выполнившего отмену
            send_notifications: Отправить уведомления

        Returns:
            Результат операции с деталями
        """
        if not entries:
            return {
                "success": True,
                "cancelled": 0,
                "message": "Нет записей для отмены",
            }

        cancelled = []
        failed = []
        refund_requests = []
        # 3808 review round 7 (P2): идемпотентные повторы (платёж уже
        # возвращён) НЕ создают строк RefundRequest — считаются отдельно,
        # чтобы refund_requests_created сообщал только реальные новые
        # заявки (финансовая честность ответа для вызывающих/аудита).
        refund_requests_existing = 0
        # 3808 review round 3 (P1 re-check under lock): entries processed
        # by a concurrent writer after our selection are skipped, never
        # refunded a second time.
        skipped = []
        notification_targets = []

        for entry in entries:
            try:
                # 3808 review round 3 (P1 re-check): fresh statement per
                # entry — READ COMMITTED re-read; an entry already processed
                # by a concurrent writer is neither cancelled again nor
                # refunded again (idempotent replay guard).
                self.db.refresh(entry)
                if entry.status not in self._PENDING_STATUSES:
                    skipped.append(
                        {"entry_id": entry.id, "status": entry.status}
                    )
                    continue

                # Получаем связанный платёж
                payment = self._get_payment_for_entry(entry)

                # Отмечаем запись как отменённую
                entry.status = "cancelled"
                entry.incomplete_reason = f"Форс-мажор: {reason}"

                refund_info = None

                if payment and payment.status == "paid" and payment.amount > 0:
                    # Создаём заявку на возврат
                    if refund_type == RefundType.DEPOSIT:
                        refund_info = self._add_to_deposit(
                            patient_id=entry.patient_id,
                            amount=payment.amount,
                            reason=reason,
                            payment_id=payment.id,
                            visit_id=entry.visit_id,
                            performed_by_id=performed_by_id,
                        )
                    else:
                        refund_info = self._create_refund_request(
                            patient_id=entry.patient_id,
                            payment_id=payment.id,
                            visit_id=entry.visit_id,
                            amount=payment.amount,
                            reason=reason,
                            refund_type=refund_type,
                            is_automatic=True,
                        )
                        # 3808 review round 7 (P2): already_refunded —
                        # идемпотентный повтор без новой строки: в счётчик
                        # НОВЫХ заявок не входит (двухочередной визит:
                        # второй банковский перенос создаёт 0 строк).
                        if refund_info.get("already_refunded"):
                            refund_requests_existing += 1
                        else:
                            refund_requests.append(refund_info)

                cancelled.append(
                    {
                        "entry_id": entry.id,
                        "patient_name": entry.patient_name,
                        "phone": entry.phone,
                        "refund_type": refund_type.value if refund_type else None,
                        "refund_amount": float(payment.amount) if payment else 0,
                        "refund_info": refund_info,
                    }
                )

                # Добавляем в список для уведомлений
                if entry.phone or entry.telegram_id:
                    notification_targets.append(
                        {
                            "phone": entry.phone,
                            "telegram_id": entry.telegram_id,
                            "patient_name": entry.patient_name,
                            "refund_type": refund_type.value if refund_type else None,
                            "refund_amount": float(payment.amount) if payment else 0,
                        }
                    )

            except Exception as e:
                logger.error(f"Ошибка при отмене записи {entry.id}: {e}")
                failed.append({"entry_id": entry.id, "error": str(e)})

        self.db.commit()

        # Отправляем уведомления
        if send_notifications and notification_targets:
            self._send_cancellation_notifications(notification_targets, reason)

        logger.info(
            f"Форс-мажор отмена: {len(cancelled)} записей отменено, "
            f"{len(failed)} ошибок, {len(skipped)} пропущено. Причина: {reason}"
        )

        return {
            "success": True,
            "cancelled": len(cancelled),
            "failed": len(failed),
            "skipped": len(skipped),
            "refund_requests_created": len(refund_requests),
            "refund_requests_existing": refund_requests_existing,
            "details": cancelled,
            "errors": failed,
            "skipped_details": skipped,
            "reason": reason,
        }

    def _get_or_create_queue(self, specialist_id: int, target_date: date) -> DailyQueue:
        """Получить или создать очередь на указанную дату

        QD-2C (Codex round-6 P1): форс-мажор перенос идёт на
        поверхность реестра — ресурсную очередь (day, tag), а не
        параллельную врачебную; теги без строки реестра сохраняют
        прежний путь врача байт-идентично.

        3808 review round 7 (P1 destination owner): этот порядок
        (реестр прежде врача) — только для вызовов БЕЗ известной
        поверхности-источника; перенос с известным источником идёт
        через ``_destination_queue`` и владельца не меняет."""
        doctor = self.db.query(Doctor).filter(Doctor.id == specialist_id).first()
        if doctor is not None and doctor.specialty:
            registry_queue = QueueApiRepository(self.db).get_or_create_registry_queue(
                day=target_date, queue_tag=doctor.specialty
            )
            if registry_queue is not None:
                return registry_queue

        return self._get_or_create_doctor_queue(specialist_id, target_date)

    def _get_or_create_doctor_queue(
        self,
        specialist_id: int,
        target_date: date,
        *,
        queue_tag: str | None | object = _SOURCE_TAG_UNSET,
    ) -> DailyQueue:
        """Врачебная (specialist-owned) поверхность на дату.

        3808 review round 7 (P1 destination owner): выделено, чтобы
        перенос из врачебной канонической строки строил назначение
        ТОЛЬКО здесь — реестровая поверхность того же тега не
        перехватывала пациентов врача.

        3808 review round 8 (P1 queue tag): вместе с владельцем
        сохраняется ТЕГ источника. Модель разрешает несколько
        активных врачебных очередей одного врача в день, различаемых
        тегом (``uq_daily_queues_active_doctor_day_tag``): консультация
        и ЭКГ кардиолога — разные поверхности. Валидированный
        источник передаёт свой ``queue_tag`` (включая ``None`` —
        источник без тега), и назначение ищется/создаётся по
        ``(day, specialist_id, effective tag, active)``: перенос
        ЭКГ-очереди не заводит пациентов в очередь консультаций.
        Без ``queue_tag`` (legacy-путь врача) — байт-идентично
        прежнему поведению: тег выводится из ``Doctor.specialty``,
        поиск по ``(specialist_id, day)`` без фильтра тега.
        """
        doctor = self.db.query(Doctor).filter(Doctor.id == specialist_id).first()
        tag_preserved = queue_tag is not _SOURCE_TAG_UNSET
        if not tag_preserved:
            queue_tag = None
            if doctor is not None and doctor.specialty:
                queue_tag = doctor.specialty.lower().replace(" ", "_")

        # This legacy doctor-owned path creates tagged DailyQueue rows too.
        # Take the same profile/tag scope before the doctor/day lock and
        # repeat the lookup under that scope to avoid a stale check-then-insert.
        lock_daily_queue_creation(
            self.db, target_date, specialist_id, queue_tag=queue_tag
        )

        destination_query = self.db.query(DailyQueue).filter(
            DailyQueue.specialist_id == specialist_id, DailyQueue.day == target_date
        )
        if tag_preserved:
            # Effective tag mirrors the uq_daily_queues_active_doctor_day_tag
            # key (COALESCE(queue_tag, '')): NULL-тег источника совпадает с
            # пустым тегом назначения и наоборот. Переиспользуется только
            # АКТИВНАЯ строка: неактивная очередь того же тега не должна
            # принять перенесённых пациентов — создаётся свежая активная
            # поверхность (partial unique это разрешает).
            destination_query = destination_query.filter(
                func.coalesce(DailyQueue.queue_tag, "") == (queue_tag or ""),
                DailyQueue.active.is_(True),
            )
        queue = destination_query.first()

        if not queue:
            queue = DailyQueue(
                day=target_date,
                specialist_id=specialist_id,
                queue_tag=queue_tag,
                active=True,
                **daily_queue_creation_snapshot(
                    self.db,
                    day=target_date,
                    doctor=doctor,
                    queue_tag=queue_tag,
                ),
            )
            self.db.add(queue)
            self.db.flush()

        return queue

    def _entries_source_queue(
        self, entries: list[OnlineQueueEntry], specialist_id: int
    ) -> DailyQueue | None:
        """3808 review round 7 (P1 destination owner): вывести поверхность
        источника из очередей самих записей, когда вызывающий слой не
        передал каноническую строку (legacy-пути entry_ids/specialist).

        Все записи во врачебных очередях ЭТОГО специалиста — врачебная
        поверхность; все в ресурсных (specialist NULL) — реестровая.
        Смешанный/неизвестный набор — None (прежний порядок реестра)."""
        queue_ids = {entry.queue_id for entry in entries}
        if not queue_ids:
            return None
        rows = (
            self.db.query(DailyQueue)
            .filter(DailyQueue.id.in_(queue_ids))
            .all()
        )
        by_id = {row.id: row for row in rows}
        resolved = [by_id.get(queue_id) for queue_id in queue_ids]
        if any(row is None for row in resolved):
            return None
        if all(row.specialist_id == specialist_id for row in resolved):
            return resolved[0]
        if all(row.specialist_id is None for row in resolved):
            return resolved[0]
        return None

    def _destination_queue(
        self,
        source_queue: DailyQueue | None,
        specialist_id: int,
        target_date: date,
    ) -> DailyQueue:
        """3808 review round 7 (P1 destination owner): очередь назначения
        сохраняет владельца источника.

        * врачебный источник (specialist_id == specialist_id) —
          ВРАЧЕБНАЯ очередь следующего дня ТОГО ЖЕ ТЕГА, что и
          источник (round 8): у врача в день могут сосуществовать
          активные очереди разных тегов — консультация и ЭКГ
          (``uq_daily_queues_active_doctor_day_tag``); реестровый
          surface и чужие теги не рассматриваются;
        * ресурсный источник (specialist_id IS NULL) — реестровая
          поверхность (day, tag) СОБСТВЕННОГО тега источника;
          поверхность дня назначения принимается только при ТОЧНОМ
          совпадении владельца с источником (specialist_id IS NULL и
          тот же queue_resource_id — round 9: tag_routes_to_resource
          готов вернуть активную врачебную очередь того же тега или
          поверхность другого ресурса); при любом несовпадении или
          недоступности реестровой строки — отказ
          (ForceMajeureError): тихо подменять владельца назначения
          нельзя;
        * источник неизвестен — прежний порядок (реестр прежде врача)."""
        if source_queue is None:
            return self._get_or_create_queue(specialist_id, target_date)

        if source_queue.specialist_id == specialist_id:
            return self._get_or_create_doctor_queue(
                specialist_id, target_date, queue_tag=source_queue.queue_tag
            )

        if source_queue.specialist_id is None:
            # 3808 review round 9 (P1 destination owner recheck):
            # поверхность (day, tag) НЕ обязана быть ресурсной строкой
            # источника — tag_routes_to_resource готов вернуть и
            # АКТИВНУЮ врачебную очередь того же тега (пока жив
            # реестровый ряд), и поверхность ДРУГОГО ресурса (после
            # перевязки тега в реестре). Сначала — ТОЛЬКО ЧТЕНИЕ:
            # кандидат принимается при ТОЧНОМ совпадении владельца с
            # источником (specialist_id IS NULL и тот же
            # queue_resource_id); любое несовпадение — fail closed
            # БЕЗ единой записи: ресурсные пациенты не переезжают на
            # чужую поверхность молча (смена владельца — явная
            # операция, не побочный эффект форс-мажора).
            routing = tag_routes_to_resource(
                self.db, source_queue.queue_tag, target_date
            )
            if routing is not None:
                if (
                    routing.specialist_id is None
                    and routing.queue_resource_id
                    == source_queue.queue_resource_id
                ):
                    return routing
                raise ForceMajeureError(
                    "Поверхность тега "
                    f"{source_queue.queue_tag!r} на "
                    f"{target_date.isoformat()} (очередь id={routing.id}) "
                    "принадлежит не ресурсу источника ("
                    f"specialist_id={routing.specialist_id!r}, "
                    f"queue_resource_id={routing.queue_resource_id!r}; "
                    "у источника queue_resource_id="
                    f"{source_queue.queue_resource_id!r}): перенос с "
                    "ресурсной очереди не может тихо сменить владельца "
                    "назначения"
                )
            # Поверхности (day, tag) ещё нет: создавать её можно
            # только из ТОГО ЖЕ ресурса, что владеет источником.
            # Перевязка тега на другой реестровый ряд или исчезновение
            # ряда — отказ, а не тихая смена владельца назначения.
            resource = resolve_tag_resource(
                self.db, source_queue.queue_tag
            )
            if (
                resource is None
                or source_queue.queue_resource_id is None
                or int(resource.id) != int(source_queue.queue_resource_id)
            ):
                raise ForceMajeureError(
                    "Реестровая поверхность тега "
                    f"{source_queue.queue_tag!r} недоступна на "
                    f"{target_date.isoformat()}"
                    + (
                        ""
                        if resource is None
                        else " (тег принадлежит другому ресурсу"
                        f" id={resource.id}, у источника id="
                        f"{source_queue.queue_resource_id})"
                    )
                    + ": перенос с ресурсной очереди не может тихо "
                    "сменить владельца назначения"
                )
            registry_queue = QueueApiRepository(
                self.db
            ).get_or_create_registry_queue(
                day=target_date, queue_tag=source_queue.queue_tag
            )
            # Создание сериализовано lock_registry_tag_creation с
            # row-locked recheck, но результату не доверяем вслепую:
            # итоговая строка обязана быть поверхностью ТОГО ЖЕ
            # ресурса (бэкстоп против гонки перевязки тега).
            if (
                registry_queue is not None
                and registry_queue.specialist_id is None
                and registry_queue.queue_resource_id
                == source_queue.queue_resource_id
            ):
                return registry_queue
            raise ForceMajeureError(
                "Поверхность тега "
                f"{source_queue.queue_tag!r} на "
                f"{target_date.isoformat()} (очередь "
                f"id={getattr(registry_queue, 'id', None)!r}) "
                "принадлежит не ресурсу источника ("
                f"specialist_id={getattr(registry_queue, 'specialist_id', None)!r}, "
                "queue_resource_id="
                f"{getattr(registry_queue, 'queue_resource_id', None)!r}; "
                "у источника queue_resource_id="
                f"{source_queue.queue_resource_id!r}): перенос с "
                "ресурсной очереди не может тихо сменить владельца "
                "назначения"
            )

        # Чужая врачебная очередь как источник — не валидируется здесь;
        # сохраняем прежний порядок для такого прямого вызова.
        return self._get_or_create_queue(specialist_id, target_date)

    def _get_payment_for_entry(self, entry: OnlineQueueEntry) -> Payment | None:
        """Получить платёж для записи"""
        if not entry.visit_id:
            return None

        visit = self.db.query(Visit).filter(Visit.id == entry.visit_id).first()
        if not visit:
            return None
        if visit.patient_id != entry.patient_id:
            raise ForceMajeureError(
                "Queue entry visit does not belong to the queue patient"
            )

        return (
            self.db.query(Payment)
            .filter(Payment.visit_id == entry.visit_id, Payment.status == "paid")
            .first()
        )

    @staticmethod
    def _already_refunded_by_claim(
        payment_id: int, claim: PaymentRefundClaim
    ) -> dict[str, Any]:
        """3808 review round 4: ответ для проигравшего гонку за возврат —
        платёж уже возвращён, указываем каким каналом (для UI/аудита)."""
        return {
            "already_refunded": True,
            "payment_id": payment_id,
            "prior_channel": claim.channel,
            "prior_deposit_transaction_id": claim.deposit_transaction_id,
            "prior_refund_request_id": claim.refund_request_id,
        }

    def _claim_is_stale(self, claim: PaymentRefundClaim) -> bool:
        """3808 round 5 (P1 claim lifecycle): claim мёртв, если его
        банковская заявка закончилась БЕЗ выплаты денег.

        * ``deposit``-канал мёртвым быть не может: зачисление на депозит —
          уже свершшееся движение денег, обратных статусов у него нет;
        * ``refund_request``-канал мёртв, когда связанная заявка в
          терминальном не-платящем статусе (rejected/cancelled) — деньги
          пациенту НЕ ушли;
        * если связанная заявка не найдена (строку удалили — FK SET NULL
          обнулил ссылку), ищем любую ЖИВУЮ автоматическую заявку этого
          платежа: есть — claim жив (fail-closed к деньгам); живых нет, но
          есть отклонённые — мёртв; нет вообще — консервативно жив
          (orphan-claim, разбирается вручную, логируем предупреждение).
        """
        if claim.channel == self.REFUND_CHANNEL_DEPOSIT:
            return False
        request = None
        if claim.refund_request_id is not None:
            request = self.db.get(RefundRequest, claim.refund_request_id)
        if request is not None:
            return request.status in self.REFUND_REQUEST_FAILED_STATUSES
        automatic_requests = (
            self.db.query(RefundRequest)
            .filter(
                RefundRequest.payment_id == claim.payment_id,
                RefundRequest.is_automatic.is_(True),
            )
            .all()
        )
        if any(
            req.status in self.REFUND_REQUEST_ACTIVE_STATUSES
            for req in automatic_requests
        ):
            return False
        if automatic_requests:
            return True
        logger.warning(
            "PaymentRefundClaim %s (payment %s, channel %s) has no bound "
            "refund request and no automatic requests — treating as live "
            "(fail-closed); investigate manually",
            claim.id,
            claim.payment_id,
            claim.channel,
        )
        return False

    def _claim_payment_refund(
        self,
        payment_id: int,
        channel: str,
        *,
        reason: str | None = None,
    ) -> int | dict[str, Any]:
        """Атомарно застолбить ЕДИНСТВЕННЫЙ возврат платежа (round 4, P1).

        3808 review round 4 (P1 cross-channel double refund): два частичных
        индекса 0087 видели только свой канал — один платёж из записей в
        РАЗНЫХ очередях мог получить и депозит, и банковскую заявку.
        Единый claim по ``payment_id`` (миграция 0088) не зависит от канала:

        * вернёт ``int`` (id claim-а) — мы выиграли право на возврат;
        * вернёт словарь already-refunded — платёж уже возвращён любым
          каналом (или конкурент выиграл гонку).

        3808 review round 5 (P1 claim lifecycle): существующий claim
        проверяется на «живость» — claim банковской заявки, отклонённой
        без выплаты, мёртв и освобождается (DELETE в этой же транзакции,
        атомарно с последующим INSERT нового claim-а). Это ленивое
        самоисцеление покрывает любой путь отклонения/отмены заявки,
        включая строки, занесённые до этого фикса.

        Savepoint берётся НА УРОВНЕ ПОДКЛЮЧЕНИЯ
        (``session.connection().begin_nested()``), а не сессии: session-level
        begin_nested ломает внешнюю savepoint-машину тестовой фикстуры
        db_session (listener after_transaction_end), а get_bind() для
        сессии, привязанной к engine, возвращает сам engine. Явный flush
        ДО savepoint выталкивает pending-изменения ORM (например,
        status="cancelled" текущей записи) НАРУЖУ отката: IntegrityError
        откатывает только INSERT claim-а, отмена записи не теряется.
        Вставка — Core, без ORM объекта: после rollback в сессии не
        остаётся рассинхронизированного состояния.
        ``uq_payment_refund_claims_payment`` — DB-бэкстоп для любых путей
        в обход сервиса.
        """
        existing = (
            self.db.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.payment_id == payment_id)
            .first()
        )
        if existing is not None:
            if self._claim_is_stale(existing):
                # 3808 round 5: терминальный не-платящий статус заявки —
                # деньги не вернулись, платёж снова доступен для возврата.
                logger.info(
                    "Releasing stale PaymentRefundClaim %s (payment %s, "
                    "channel %s): bound refund request ended without a payout",
                    existing.id,
                    payment_id,
                    existing.channel,
                )
                self.db.delete(existing)
                self.db.flush()
            else:
                return self._already_refunded_by_claim(payment_id, existing)

        # Pending-изменения ORM — наружу savepoint (см. docstring).
        self.db.flush()
        bind = self.db.connection()
        try:
            with bind.begin_nested():
                result = self.db.execute(
                    insert(PaymentRefundClaim)
                    .values(payment_id=payment_id, channel=channel, reason=reason)
                )
        except IntegrityError:
            # Проиграли гонку за платёж: другая транзакция закоммитила
            # (или держит) claim — в READ COMMITTED после ожидания на
            # уникальном индексе победитель уже виден. Деньги не двигаем.
            winner = (
                self.db.query(PaymentRefundClaim)
                .filter(PaymentRefundClaim.payment_id == payment_id)
                .first()
            )
            if winner is not None:
                return self._already_refunded_by_claim(payment_id, winner)
            return {
                "already_refunded": True,
                "payment_id": payment_id,
                "prior_channel": channel,
                "conflict": "unique_payment_refund_claim",
            }
        return int(result.inserted_primary_key[0])

    def _add_to_deposit(
        self,
        patient_id: int,
        amount: float,
        reason: str,
        payment_id: int,
        visit_id: int | None,
        performed_by_id: int,
    ) -> dict[str, Any]:
        """Добавить средства на депозит пациента

        3808 review round 3 (P1 double refund): IDEMPOTENT per payment —
        if this payment was already credited (a previous force-majeure
        leg), no second credit row and no balance change; the caller's
        entry is still cancelled, the money is not moved twice. The
        ``uq_deposit_transactions_credit_payment`` partial unique index
        is the DB-level backstop for whatever this pre-check could miss
        (see 0087 migration).

        3808 review round 4 (P1 cross-channel double refund): защита
        теперь ЕДИНАЯ по payment_id, а не по каналу. Кредит на депозит не
        создаётся, если платёж уже возвращён ЛЮБОЙ автоматической ногой —
        в том числе автоматической заявкой на банковский возврат из
        отмены ДРУГОЙ очереди, где тот же визит остался в записях.
        Право на возврат атомарно занимается в ``payment_refund_claims``
        (миграция 0088) ДО первого денежного изменения.
        """
        from decimal import Decimal

        amount_decimal = Decimal(str(amount))

        existing_credit = (
            self.db.query(DepositTransaction)
            .filter(
                DepositTransaction.payment_id == payment_id,
                DepositTransaction.transaction_type
                == DepositTransactionType.CREDIT.value,
            )
            .first()
        )
        if existing_credit is not None:
            return {
                "type": "deposit",
                "deposit_id": existing_credit.deposit_id,
                "amount": float(existing_credit.amount),
                "already_refunded": True,
                "payment_id": payment_id,
                "prior_channel": self.REFUND_CHANNEL_DEPOSIT,
            }

        # 3808 round 4: кросс-канальная проверка — платёж уже уходит
        # банковским возвратом (строки могло не быть в claim-ах, если она
        # создана до 0088 или напрямую, как в тестах). 3808 round 5:
        # учитываются только ЖИВЫЕ заявки — отклонённая/отменённая заявка
        # денег не вернула и повторному возврату не мешает.
        prior_request = (
            self.db.query(RefundRequest)
            .filter(
                RefundRequest.payment_id == payment_id,
                RefundRequest.is_automatic.is_(True),
                RefundRequest.status.in_(self.REFUND_REQUEST_ACTIVE_STATUSES),
            )
            .first()
        )
        if prior_request is not None:
            return {
                "type": "deposit",
                "already_refunded": True,
                "payment_id": payment_id,
                "prior_channel": self.REFUND_CHANNEL_REFUND_REQUEST,
                "prior_request_id": prior_request.id,
            }

        claim_id = self._claim_payment_refund(
            payment_id, self.REFUND_CHANNEL_DEPOSIT, reason=reason
        )
        if isinstance(claim_id, dict):
            return {"type": "deposit", **claim_id}

        # Получаем или создаём депозит пациента
        deposit = (
            self.db.query(PatientDeposit)
            .filter(PatientDeposit.patient_id == patient_id)
            .first()
        )

        if not deposit:
            deposit = PatientDeposit(patient_id=patient_id, balance=amount_decimal)
            self.db.add(deposit)
        else:
            deposit.balance += amount_decimal

        self.db.flush()

        # Создаём транзакцию
        transaction = DepositTransaction(
            deposit_id=deposit.id,
            transaction_type=DepositTransactionType.CREDIT.value,
            amount=amount_decimal,
            balance_after=deposit.balance,
            description=f"Возврат (форс-мажор): {reason}",
            payment_id=payment_id,
            visit_id=visit_id,
            performed_by=performed_by_id,
        )
        self.db.add(transaction)
        self.db.flush()  # нужен id транзакции для аудита claim-а

        # Аудит единого claim-а: какая строка осуществила возврат
        claim_row = self.db.get(PaymentRefundClaim, claim_id)
        claim_row.deposit_transaction_id = transaction.id

        return {
            "type": "deposit",
            "deposit_id": deposit.id,
            "amount": float(amount_decimal),
            "new_balance": float(deposit.balance),
            "refund_claim_id": claim_id,
        }

    def _create_refund_request(
        self,
        patient_id: int,
        payment_id: int,
        visit_id: int | None,
        amount: float,
        reason: str,
        refund_type: RefundType,
        is_automatic: bool = False,
    ) -> dict[str, Any]:
        """Создать заявку на возврат

        3808 review round 3 (P1 double refund): IDEMPOTENT for the
        automatic (force majeure) leg — an existing automatic request for
        the same payment is returned instead of a duplicate; manual
        cashier requests (is_automatic=False) are not constrained here.
        The ``uq_refund_requests_auto_payment`` partial unique index is
        the DB-level backstop (see 0087 migration).

        3808 review round 4 (P1 cross-channel double refund): как и в
        ``_add_to_deposit``, защита ЕДИНАЯ по payment_id: автоматическая
        заявка не создаётся, если платёж уже возвращён зачислением на
        депозит (например, отменой другой очереди, где тот же визит
        остался в записях). Атомарный арбитр — ``payment_refund_claims``
        (миграция 0088); ручные кассовые заявки по-прежнему не
        ограничены — как и в предикате 0087.

        3808 review round 5 (P1 claim lifecycle): блокирующая проверка и
        предикат 0087 учитывают только ЖИВЫЕ заявки
        (pending/approved/processing/completed). Отклонённая или
        отменённая заявка денег не вернула: повторная АВТОМАТИЧЕСКАЯ
        заявка (например, с исправленными реквизитами) создаётся
        свободно, а её claim займёт освободившийся слот платежа.
        """
        from decimal import Decimal

        amount_decimal = Decimal(str(amount))

        existing_request = (
            self.db.query(RefundRequest)
            .filter(
                RefundRequest.payment_id == payment_id,
                RefundRequest.is_automatic.is_(True),
                RefundRequest.status.in_(self.REFUND_REQUEST_ACTIVE_STATUSES),
            )
            .first()
        )
        if existing_request is not None:
            return {
                "type": "refund_request",
                "request_id": existing_request.id,
                "amount": float(existing_request.refund_amount),
                "status": existing_request.status,
                "already_refunded": True,
                "payment_id": payment_id,
                "prior_channel": self.REFUND_CHANNEL_REFUND_REQUEST,
            }

        claim_id: int | None = None
        if is_automatic:
            # 3808 round 4: кросс-канальная проверка — платёж уже
            # зачислен на депозит (строка могла быть создана до 0088).
            prior_credit = (
                self.db.query(DepositTransaction)
                .filter(
                    DepositTransaction.payment_id == payment_id,
                    DepositTransaction.transaction_type
                    == DepositTransactionType.CREDIT.value,
                )
                .first()
            )
            if prior_credit is not None:
                return {
                    "type": "refund_request",
                    "already_refunded": True,
                    "payment_id": payment_id,
                    "prior_channel": self.REFUND_CHANNEL_DEPOSIT,
                    "prior_deposit_transaction_id": prior_credit.id,
                }

            claim_id = self._claim_payment_refund(
                payment_id, self.REFUND_CHANNEL_REFUND_REQUEST, reason=reason
            )
            if isinstance(claim_id, dict):
                return {"type": "refund_request", **claim_id}

        refund_request = RefundRequest(
            patient_id=patient_id,
            payment_id=payment_id,
            visit_id=visit_id,
            original_amount=amount_decimal,
            refund_amount=amount_decimal,
            commission_amount=Decimal("0"),
            refund_type=refund_type.value,
            status=RefundRequestStatus.PENDING.value,
            reason=reason,
            is_automatic=is_automatic,
        )
        self.db.add(refund_request)
        self.db.flush()

        # Аудит единого claim-а: какая заявка осуществила возврат
        if claim_id is not None:
            claim_row = self.db.get(PaymentRefundClaim, claim_id)
            claim_row.refund_request_id = refund_request.id

        return {
            "type": "refund_request",
            "request_id": refund_request.id,
            "amount": float(amount_decimal),
            "status": refund_request.status,
            "refund_claim_id": claim_id,
        }

    def _send_transfer_notifications(
        self, targets: list[dict[str, Any]], reason: str
    ) -> None:
        """Отправить уведомления о переносе"""
        for target in targets:
            try:
                _message = (
                    f"Уважаемый(ая) {target['patient_name']}!\n\n"
                    f"Ваша запись перенесена на {target['new_date'].strftime('%d.%m.%Y')}.\n"
                    f"Ваш новый номер в очереди: {target['new_number']}\n"
                    f"Вы будете одним из первых в очереди.\n\n"
                    f"Причина: {reason}\n\n"
                    f"Приносим извинения за неудобства."
                )

                # Отправка через Telegram
                if target.get("telegram_id"):
                    try:
                        # TODO: Интеграция с Telegram service
                        pass
                    except Exception as e:
                        logger.warning(f"Telegram notification failed: {e}")

                # Отправка Push уведомления
                # TODO: Получить FCM токен по patient_id и отправить

            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")

    def _send_cancellation_notifications(
        self, targets: list[dict[str, Any]], reason: str
    ) -> None:
        """Отправить уведомления об отмене"""
        for target in targets:
            try:
                refund_info = ""
                if target.get("refund_amount") and target["refund_amount"] > 0:
                    if target.get("refund_type") == "deposit":
                        refund_info = (
                            f"\n💰 Средства ({target['refund_amount']:,.0f} UZS) "
                            f"зачислены на ваш депозит в клинике."
                        )
                    else:
                        refund_info = (
                            f"\n💰 Создана заявка на возврат ({target['refund_amount']:,.0f} UZS). "
                            f"С вами свяжется менеджер."
                        )

                _message = (
                    f"Уважаемый(ая) {target['patient_name']}!\n\n"
                    f"К сожалению, ваша запись отменена.\n"
                    f"Причина: {reason}"
                    f"{refund_info}\n\n"
                    f"Приносим извинения за неудобства."
                )

                # Отправка через Telegram
                if target.get("telegram_id"):
                    try:
                        # TODO: Интеграция с Telegram service
                        pass
                    except Exception as e:
                        logger.warning(f"Telegram notification failed: {e}")

            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")


# Factory function
def get_force_majeure_service(db: Session) -> ForceMajeureService:
    """Получить экземпляр сервиса форс-мажора"""
    return ForceMajeureService(db)
