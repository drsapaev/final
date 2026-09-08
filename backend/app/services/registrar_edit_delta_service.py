from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, attributes

from app.crud.patient import normalize_patient_name
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.queue_service import queue_service
from app.services.service_mapping import get_service_code, normalize_service_code

ACTIVE_APPEND_STATUSES = ("waiting", "called", "in_service", "diagnostics")

# W2-PR1: позиции визита в этих статусах нельзя изменять через edit-delta:
# "closed" — услуга уже выполнена (потреблённый объём не корректируется
# редактированием корзины), "canceled" — деньги прошли цепочку отмены,
# "paid" — legacy-статус. Снижение по оплаченному счёту = возврат —
# отдельный финансовый контракт (wave2 PR3), а не побочный эффект редактирования.
# Codex R9 PR 3115 (P1): "expired" — терминальный статус по SSOT
# visit_lifecycle_service (истёкшее подтверждение). Пропуск expired давал две
# дыры: снижение мутировало терминальный визит, чья запись оставалась
# appendable; а если запись уже не appendable, _assert_service_not_on_blocked_visit
# тоже не находила визит — команда создавала дубликат визита для той же услуги
# и дня.
VISIT_POSITION_BLOCKED_STATUSES = ("closed", "canceled", "paid", "expired")


@dataclass(frozen=True)
class RegistrarEditDeltaItem:
    service_id: int
    quantity: int = 1
    specialist_id: int | None = None
    # Codex R8 #3115 (P1): идентичность исходной записи позиции. При одном
    # service_id под разными врачами/записями только она определяет, ЧЬЯ
    # позиция правится: глобальный preferred-набор выбирал бы ближайшую
    # запись и мог мутировать позицию врача A при правке строки врача B.
    queue_entry_id: int | None = None


class RegistrarEditDeltaService:
    """Append edit-mode service deltas without duplicating active queue rows."""

    def __init__(self, db: Session):
        self.db = db

    def apply(
        self,
        *,
        patient_id: int,
        services: list[RegistrarEditDeltaItem],
        target_date: date,
        payment_method: str,
        discount_mode: str,
        all_free: bool,
        patient_data: dict[str, Any] | None = None,
        existing_queue_entry_ids: list[int] | None = None,
        expected_entry_updated_at: dict[int, str] | None = None,
        current_user: User | None = None,
    ) -> dict[str, Any]:
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")

        queue_entry_ids = set(existing_queue_entry_ids or [])

        # W2-PR2: каноническая дата редактирования. Редактируем ТЕ записи,
        # которые названы в existing_queue_entry_ids, поэтому их день —
        # единственный допустимый target_date. Прежний контракт «фронт шлёт
        # getLocalISODate()» молча переносил правку записи на будущую дату
        # в «сегодня» (визит создавался today, исходная запись оставалась
        # нетронутой — дата терялась).
        target_date = self.resolve_edit_target_day(
            patient_id=patient_id,
            preferred_entry_ids=queue_entry_ids,
            requested_target_date=target_date,
        )

        # R-08 fix: optimistic locking — проверяем что existing entries не были
        # изменены другим пользователем с момента последнего чтения frontend'ом.
        if expected_entry_updated_at:
            self._assert_entries_not_concurrently_modified(
                expected_entry_updated_at
            )

        if patient_data:
            self._apply_patient_data(patient, patient_data)

        queue_numbers: dict[int, list[dict[str, Any]]] = {}
        visit_delta_amounts: dict[int, Decimal] = {}
        updated_queue_entries: list[dict[str, Any]] = []
        created_visit_payloads: dict[int, dict[str, Any]] = {}

        for item in services:
            service = self.db.query(Service).filter(Service.id == item.service_id).first()
            if not service:
                raise ValueError(f"Service {item.service_id} not found")

            queue_tag = service.queue_tag or service.department_key
            if not queue_tag:
                raise ValueError(f"Service {service.id} has no queue tag")

            requested_qty = max(int(item.quantity or 1), 1)
            # Codex R8 #3115 (P1): индивидуальная маршрутизация позиции —
            # явная запись позиции имеет приоритет над глобальным набором.
            item_preferred: set[int] = (
                {int(item.queue_entry_id)}
                if item.queue_entry_id is not None
                else queue_entry_ids
            )
            entry = self._find_active_entry(
                patient_id=patient_id,
                queue_tag=queue_tag,
                target_date=target_date,
                preferred_entry_ids=item_preferred,
                specialist_id=item.specialist_id,
                # Codex R8 #3115 (P1): мутирующая команда фиксирует выбранную
                # запись до конца транзакции.
                lock=True,
                # Codex R11 #3115 (P1): явно названный ID — строгий селектор,
                # а не мягкое предпочтение: устаревшая идентичность — 400.
                strict_entry_id=(
                    int(item.queue_entry_id) if item.queue_entry_id is not None else None
                ),
            )

            if entry:
                delta = self._append_to_existing_entry(
                    entry=entry,
                    patient=patient,
                    service=service,
                    requested_qty=requested_qty,
                    target_date=target_date,
                    specialist_id=item.specialist_id,
                    discount_mode=discount_mode,
                    all_free=all_free,
                    current_user=current_user,
                )
            else:
                # W2-PR1: активной записи нет. Два громких отказа вместо
                # ложного «добавления»:
                # 1) услуга уже выполнена/отменена в этот день — правка
                #    количества создала бы дубликат позиции;
                # 2) позиция уже существует у другого врача, а запрос явно
                #    называет иного специалиста — это перенос (wave2 PR2),
                #    а не добавление: иначе услуга задвоилась бы.
                self._assert_service_not_on_blocked_visit(
                    patient_id=patient_id,
                    service_id=service.id,
                    target_date=target_date,
                )
                self._assert_not_doctor_change_of_existing_position(
                    patient_id=patient_id,
                    service=service,
                    target_date=target_date,
                    preferred_entry_ids=item_preferred,
                    specialist_id=item.specialist_id,
                )
                delta = self._create_new_queue_entry(
                    patient=patient,
                    service=service,
                    requested_qty=requested_qty,
                    target_date=target_date,
                    specialist_id=item.specialist_id,
                    discount_mode=discount_mode,
                    all_free=all_free,
                    current_user=current_user,
                )

            # W2-PR1: в финансовую дельту попадает ЛЮБАЯ ненулевая дельта —
            # в том числе отрицательная (снижение). Прежний фильтр > 0
            # выбрасывал снижение из инвойс-расчёта полностью.
            if delta["delta_amount"] != 0 and delta["visit_id"]:
                visit_id = int(delta["visit_id"])
                visit_delta_amounts[visit_id] = (
                    visit_delta_amounts.get(visit_id, Decimal("0"))
                    + delta["delta_amount"]
                )
            # created_visits (для пост-мастерового экрана) описывает только
            # доначисления; снижение не «создаёт» услугу.
            if delta["delta_amount"] > 0 and delta["visit_id"]:
                visit_id = int(delta["visit_id"])
                created_visit_payloads.setdefault(
                    visit_id,
                    {
                        "visit_id": visit_id,
                        "patient_name": patient.short_name(),
                        "doctor_name": self._doctor_name(delta.get("doctor_id")),
                        "visit_date": target_date.isoformat(),
                        "visit_time": None,
                        "status": "open",
                        "department": service.department_key or service.queue_tag,
                        "services": [],
                        "confirmation_required": False,
                        "confirmation_token": None,
                    },
                )
                created_visit_payloads[visit_id]["services"].append(
                    self._service_response_payload(
                        service=service,
                        quantity=delta["delta_quantity"],
                        price=delta["unit_price"],
                    )
                )

            if delta["visit_id"]:
                queue_numbers.setdefault(int(delta["visit_id"]), [])
                assignment = {
                    "queue_tag": queue_tag,
                    "queue_id": delta["queue_id"],
                    "number": delta["number"],
                    "status": delta["queue_status"],
                    "queue_entry_id": delta["queue_entry_id"],
                }
                if assignment not in queue_numbers[int(delta["visit_id"])]:
                    queue_numbers[int(delta["visit_id"])].append(assignment)

            updated_queue_entries.append(
                {
                    "queue_entry_id": delta["queue_entry_id"],
                    "queue_id": delta["queue_id"],
                    "queue_tag": queue_tag,
                    "number": delta["number"],
                    "status": delta["queue_status"],
                    "visit_id": delta["visit_id"],
                    "delta_quantity": delta["delta_quantity"],
                    "delta_amount": delta["delta_amount"],
                }
            )

        total_amount = sum(visit_delta_amounts.values(), Decimal("0"))
        invoice = self._apply_invoice_delta(
            patient_id=patient_id,
            payment_method=payment_method,
            visit_delta_amounts=visit_delta_amounts,
            total_amount=total_amount,
        )

        self.db.commit()

        return {
            "success": True,
            # W2-PR2: фактическая дата, в которую легли правки (день
            # редактируемых записей, не обязательно запрошенная).
            "target_date": target_date.isoformat(),
            "message": (
                "Запись обновлена. Добавленные услуги сохранены в существующей очереди."
                if total_amount > 0
                else (
                    "Запись обновлена. Сумма счёта уменьшена."
                    if total_amount < 0
                    else "Запись обновлена. Новых платных услуг не добавлено."
                )
            ),
            "invoice_id": invoice.id if invoice else None,
            "visit_ids": list(visit_delta_amounts.keys()),
            "total_amount": total_amount,
            "queue_numbers": queue_numbers,
            "print_tickets": [],
            "created_visits": list(created_visit_payloads.values()),
            "updated_queue_entries": updated_queue_entries,
        }

    def _assert_entries_not_concurrently_modified(
        self,
        expected_entry_updated_at: dict[int, str],
    ) -> None:
        """R-08 fix: optimistic locking via updated_at.

        Проверяет что ни одна из existing queue entries не была изменена
        другим пользователем с момента последнего чтения frontend'ом.

        Если хотя бы одна entry изменилась — raises ValueError (caller maps to 400).
        Это предотвращает silent data loss когда два регистратора одновременно
        редактируют одного пациента (добавляют услуги, меняют количество и т.д.).
        """

        entry_ids = list(expected_entry_updated_at.keys())
        if not entry_ids:
            return

        entries = (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id.in_(entry_ids))
            .all()
        )
        entries_by_id = {e.id: e for e in entries}

        for entry_id, expected_iso in expected_entry_updated_at.items():
            entry = entries_by_id.get(entry_id)
            if entry is None:
                # Entry уже удалена другим пользователем
                raise ValueError(
                    f"Запись очереди #{entry_id} была удалена другим пользователем. "
                    "Обновите страницу, чтобы получить актуальные данные."
                )

            try:
                expected_dt = datetime.fromisoformat(
                    expected_iso.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                # graceful degradation: не блокируем если не удалось распарсить
                continue

            # Нормализуем оба к timezone-aware UTC для сравнения
            if expected_dt.tzinfo is None:
                expected_dt = expected_dt.replace(tzinfo=UTC)

            actual_dt = entry.updated_at
            if actual_dt is None:
                continue
            if actual_dt.tzinfo is None:
                actual_dt = actual_dt.replace(tzinfo=UTC)

            # Допускаем 1 секунду разницы (clock skew, округление БД)
            if abs((actual_dt - expected_dt).total_seconds()) > 1:
                raise ValueError(
                    f"Запись очереди #{entry_id} была изменена другим пользователем. "
                    "Обновите страницу, чтобы получить актуальные данные."
                )

    def _assert_service_not_on_blocked_visit(
        self,
        *,
        patient_id: int,
        service_id: int,
        target_date: date,
    ) -> None:
        """W2-PR1: изменение завершённой/отменённой позиции дня — не no-op и
        не добавление: явный отказ вместо дубликата или имитации сохранения.

        Скоуп — тот же день, что и целевая дата команды: выполненная услуга
        прошлых дней не мешает новой записи на target_date (легитимный
        повторный визит). Перенос целевой даты на исходную дату визита —
        контракт wave2 PR2."""
        blocked = (
            self.db.query(VisitService)
            .join(Visit, Visit.id == VisitService.visit_id)
            .filter(
                Visit.patient_id == patient_id,
                VisitService.service_id == service_id,
                Visit.visit_date == target_date,
                Visit.status.in_(VISIT_POSITION_BLOCKED_STATUSES),
            )
            .first()
        )
        if blocked:
            raise ValueError(
                "Услуга уже выполнена или отменена в этот день — изменение количества "
                "недоступно. Для корректировки используйте отмену/корректировку визита"
            )

    def _assert_not_doctor_change_of_existing_position(
        self,
        *,
        patient_id: int,
        service: Service,
        target_date: date,
        preferred_entry_ids: set[int],
        specialist_id: int | None,
    ) -> None:
        """W2-PR1: явный specialist_id при позиции, уже существующей в
        активной записи ДРУГОГО врача того же queue_tag — это перенос
        позиции, а не добавление. Прежний матчинг молча возвращал None и
        команда создавала вторую позицию под новым врачом, оставляя старую —
        двойное начисление при намерении «перенести».

        Контракт переноса записи — отдельная операция (wave2 PR2): здесь
        громкий отказ с причиной. Без явного specialist_id — прежняя
        маршрутизация (проверка не применяется)."""
        if specialist_id is None:
            return
        queue_tag = service.queue_tag or service.department_key
        entries = (
            self.db.query(OnlineQueueEntry)
            .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
            .filter(
                OnlineQueueEntry.patient_id == patient_id,
                OnlineQueueEntry.status.in_(ACTIVE_APPEND_STATUSES),
                DailyQueue.day == target_date,
                DailyQueue.queue_tag == queue_tag,
                DailyQueue.active.is_(True),
            )
            .all()
        )
        if preferred_entry_ids:
            entries = [entry for entry in entries if entry.id in preferred_entry_ids]
        for entry in entries:
            payload = self._find_service_payload(
                self._coerce_services(entry.services), service
            )
            if payload is None:
                continue
            queue_specialist = entry.queue.specialist_id if entry.queue else None
            if queue_specialist is not None and int(queue_specialist) != int(specialist_id):
                raise ValueError(
                    f"Услуга «{service.name}» уже записана к другому врачу. "
                    "Смена врача существующей услуги выполняется переносом записи — "
                    "обратитесь к администратору"
                )

    def _assert_decrease_allowed(self, *, entry: OnlineQueueEntry) -> None:
        """W2-PR1: снижение количества допустимо только для ещё не потреблённых
        и не оплаченных позиций.

        - визит закрыт/отменён (legacy "paid") — объём потреблён или деньги
          прошли цепочку отмены: редактирование корзины не корректирует это;
        - по визиту есть ОПЛАЧЕННЫЙ счёт — уменьшение = возврат, это отдельный
          финансовый контракт (wave2 PR3), а не побочный эффект редактирования.
        Оба случая отвергаются с явной причиной вместо имитации сохранения.
        """
        if not entry.visit_id:
            return
        visit = self.db.query(Visit).filter(Visit.id == entry.visit_id).first()
        if visit is None:
            return
        if visit.status in VISIT_POSITION_BLOCKED_STATUSES:
            raise ValueError(
                "Услуга уже выполнена или отменена — уменьшение количества недоступно. "
                "Для корректировки используйте отмену/корректировку визита"
            )
        paid = (
            self.db.query(PaymentInvoice)
            .join(PaymentInvoiceVisit, PaymentInvoiceVisit.invoice_id == PaymentInvoice.id)
            .filter(
                PaymentInvoiceVisit.visit_id == visit.id,
                PaymentInvoice.status == "paid",
            )
            .first()
        )
        if paid:
            raise ValueError(
                "По услуге есть оплаченный счёт — уменьшение количества выполняется "
                "через возврат/корректировку оплаты"
            )
        # Codex R8 #3115 (P1): счёт в статусе processing — платёж уже уходит
        # провайдеру. Снижение изменило бы очередь/визит, но редукция вычитает
        # только PENDING-счета, поэтому processing-счёт остался бы на прежнюю
        # сумму — пациент был бы обязан за старое количество. Корректировка —
        # через скоординированную платёжную операцию, не через edit-delta.
        processing = (
            self.db.query(PaymentInvoice)
            .join(PaymentInvoiceVisit, PaymentInvoiceVisit.invoice_id == PaymentInvoice.id)
            .filter(
                PaymentInvoiceVisit.visit_id == visit.id,
                PaymentInvoice.status == "processing",
            )
            .first()
        )
        if processing:
            raise ValueError(
                "По услуге идёт обработка платежа — уменьшение количества недоступно, "
                "дождитесь завершения оплаты или обратитесь в кассу"
            )
        # Codex R9 PR 3115 (P1): канонические строки Payment проверяются
        # ОТДЕЛЬНО от PaymentInvoice. Платёжные потоки (например, подтверждение
        # кассиром) коммитят Payment со статусом paid/completed БЕЗ синхронной
        # записи PaymentInvoice — счёт может отсутствовать или оставаться
        # pending. Гард выше такие визиты пропускал, и edit-delta снижал
        # услугу и даже уменьшал устаревший pending-счёт без возврата денег.
        # Деньги получены (или уже уходят провайдеру) — снижение количества
        # возможно только через возврат/корректировку оплаты.
        payment_taken = (
            self.db.query(Payment)
            .filter(
                Payment.visit_id == visit.id,
                Payment.status.in_(("paid", "processing", "completed")),
            )
            .first()
        )
        if payment_taken:
            raise ValueError(
                "По услуге зарегистрирована оплата — уменьшение количества выполняется "
                "через возврат/корректировку оплаты"
            )

    def _apply_patient_data(self, patient: Patient, patient_data: dict[str, Any]) -> None:
        if patient_data.get("full_name"):
            names = normalize_patient_name(full_name=patient_data["full_name"])
            if names["last_name"]:
                patient.last_name = names["last_name"]
            if names["first_name"]:
                patient.first_name = names["first_name"]
            patient.middle_name = names["middle_name"]
        for attr in ("phone", "address"):
            if patient_data.get(attr) is not None:
                setattr(patient, attr, patient_data[attr])
        if patient_data.get("sex") is not None:
            patient.sex = patient_data["sex"]
        if patient_data.get("birth_date") is not None:
            patient.birth_date = patient_data["birth_date"]

    def resolve_edit_target_day(
        self,
        *,
        patient_id: int,
        preferred_entry_ids: set[int] | list[int],
        requested_target_date: date,
    ) -> date:
        """W2-PR2: каноническая дата редактирования = день редактируемых записей.

        preferred-записи (existing_queue_entry_ids) — единственный источник
        истины о дате: их очередь (DailyQueue.day) определяет, ГДЕ искать
        активные позиции и КОГДА создавать новые визиты. Запрошенная дата
        используется только когда preferred не названы вовсе (флоу без
        существующих записей) или ни одна из названных не активна — прежнее
        поведение сохраняется, ничего не канонизируется молча в обход данных.

        Мультидневный набор preferred — громкий отказ: правки разных дней
        одной командой создали бы выбор «какой визит имеется в виду», который
        может сделать только оператор (продуктовое решение, см. W2-PR2 PR).
        """
        ids = {int(i) for i in (preferred_entry_ids or set())}
        if not ids:
            return requested_target_date
        rows = (
            self.db.query(OnlineQueueEntry.id, DailyQueue.day)
            .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
            .filter(
                OnlineQueueEntry.id.in_(ids),
                OnlineQueueEntry.patient_id == patient_id,
                OnlineQueueEntry.status.in_(ACTIVE_APPEND_STATUSES),
                DailyQueue.active.is_(True),
            )
            .all()
        )
        days = {row.day for row in rows}
        if not days:
            return requested_target_date
        if len(days) > 1:
            day_list = ", ".join(sorted(day.isoformat() for day in days))
            raise ValueError(
                "Выбранные записи относятся к разным датам "
                f"({day_list}). Редактирование записей разных дат одной "
                "операцией недоступно — откройте каждую дату отдельно"
            )
        return days.pop()

    def _find_active_entry(
        self,
        *,
        patient_id: int,
        queue_tag: str,
        target_date: date,
        preferred_entry_ids: set[int],
        specialist_id: int | None = None,
        lock: bool = False,
        strict_entry_id: int | None = None,
    ) -> OnlineQueueEntry | None:
        # Codex R8 #3115 (P1): lock=True фиксирует выбранную запись до конца
        # транзакции (SELECT ... FOR UPDATE) — отмена/смена статуса между
        # ревалидацией квоты и применением команды не может сменить
        # наблюдаемое состояние (READ COMMITTED).
        query = self.db.query(OnlineQueueEntry).join(
            DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id
        )
        if lock:
            query = query.with_for_update()
        entries = query.filter(
            OnlineQueueEntry.patient_id == patient_id,
            OnlineQueueEntry.status.in_(ACTIVE_APPEND_STATUSES),
            DailyQueue.day == target_date,
            DailyQueue.queue_tag == queue_tag,
            DailyQueue.active.is_(True),
        ).order_by(OnlineQueueEntry.queue_time.asc(), OnlineQueueEntry.id.asc()).all()
        if preferred_entry_ids:
            preferred = [entry for entry in entries if entry.id in preferred_entry_ids]
            if preferred:
                entries = preferred
            elif strict_entry_id is not None:
                # Codex R11 #3115 (P1): явный queue_entry_id — СТРОГИЙ селектор.
                # Прежний код при пустом preferred оставлял полный список
                # кандидатов (entries[0] — мутировала и биллила ЧУЖУЮ строку
                # очереди) или проваливался в создание новой записи (тихая
                # ре-регистрация). Устаревшая идентичность — громкий отказ.
                raise ValueError(
                    f"Указанная запись очереди ({strict_entry_id}) больше не "
                    "активна в этот день — обновите данные записи и повторите "
                    "попытку"
                )
        if specialist_id is not None:
            # W2-PR1 (ADR-001): очередь принадлежит врачу. Явно запрошенный
            # специалист не может дослать позицию в чужую очередь того же
            # queue_tag — одинаковая услуга у разных врачей не сливается
            # только из-за одинакового service_id.
            same_specialist = [
                entry
                for entry in entries
                if entry.queue is not None
                and entry.queue.specialist_id is not None
                and int(entry.queue.specialist_id) == int(specialist_id)
            ]
            return same_specialist[0] if same_specialist else None
        return entries[0] if entries else None

    def _append_to_existing_entry(
        self,
        *,
        entry: OnlineQueueEntry,
        patient: Patient,
        service: Service,
        requested_qty: int,
        target_date: date,
        specialist_id: int | None,
        discount_mode: str,
        all_free: bool,
        current_user: User | None,
    ) -> dict[str, Any]:
        services = self._coerce_services(entry.services)
        existing_payload = self._find_service_payload(services, service)
        existing_qty = self._payload_quantity(existing_payload) if existing_payload else 0

        # W2-PR1: смена врача существующей позиции не игнорируется молча.
        # Перенос позиции к другому врачу — операция переноса записи (own
        # contract), а не побочный эффект редактирования корзины: отвергаем
        # с явной причиной вместо имитации сохранения.
        if specialist_id is not None and existing_payload is not None:
            queue_specialist = entry.queue.specialist_id if entry.queue else None
            if queue_specialist is not None and int(queue_specialist) != int(specialist_id):
                raise ValueError(
                    f"Услуга «{service.name}» уже записана к другому врачу. "
                    "Смена врача существующей услуги выполняется переносом записи — "
                    "обратитесь к администратору"
                )

        # W2-PR1: ЗНАКОВАЯ дельта до целевого состояния. Item несёт ПОЛНОЕ
        # целевое количество позиции: рост биллит (target − current), снижение
        # — отрицательный остаток. Прежний max(target − current, 0) молча
        # проглатывал уменьшение количества (сохранение «успешно», состояние
        # без изменений).
        delta_qty = requested_qty - existing_qty if existing_payload else requested_qty
        if delta_qty < 0:
            self._assert_decrease_allowed(entry=entry)
        unit_price = Decimal("0") if all_free else Decimal(str(service.price or 0))
        # Снижение вычитает фактически начисленную сумму позиции (цена из
        # payload), а не текущую цену каталога — иначе entry.total_amount
        # разошёлся бы с тем, что реально выставлено ранее.
        # Codex R8 #3115 (P1): снижение вычитает ФАКТИЧЕСКИ записанную цену
        # за единицу (см. _recorded_unit_charge), а не цену каталога и не
        # line-total из payload full-update-строки.
        decrease_unit_price = (
            self._recorded_unit_charge(entry=entry, payload=existing_payload, previous_qty=existing_qty)
            if (delta_qty < 0 and existing_payload and existing_payload.get("price") is not None)
            else unit_price
        )
        delta_amount = (decrease_unit_price if delta_qty < 0 else unit_price) * Decimal(delta_qty)

        # Codex R10 #3115 (P1): рост ПЕРЕОЦЕНИВАЕТ позицию средневзвешенной
        # ценой за единицу: старые единицы сохраняют фактически записанную
        # стоимость, добавленные биллятся по текущей каталоговой (delta_amount).
        # Иначе VisitService/entry-пейлоад переписывали бы ВСЕ единицы на новую
        # каталоговую цену, хотя счёт выставляет только дельту: визит 1×100
        # при росте до 2 по цене 150 давал VisitService 2×150=300 против
        # invoice 100+150=250 — PaymentInvariantService.compute_total_cost
        # считал бы 300 канонической стоимостью визита и собирал бы лишние 50.
        # Средневзвешенная цена согласует representations: строка VisitService
        # (qty × blended) == payload (qty × blended) == entry.total_amount
        # == invoice (записанный итог + дельта).
        row_unit_price = unit_price
        if delta_qty > 0 and existing_payload:
            previous_recorded_unit = self._recorded_unit_charge(
                entry=entry, payload=existing_payload, previous_qty=existing_qty
            )
            blended_unit = (
                previous_recorded_unit * Decimal(existing_qty) + delta_amount
            ) / Decimal(requested_qty)
            row_unit_price = blended_unit.quantize(Decimal("0.01"))
            existing_payload["price"] = float(row_unit_price)
            existing_payload["unit_price"] = float(row_unit_price)

        changed_at = queue_service.get_local_timestamp(self.db)

        if delta_qty != 0:
            if existing_payload:
                existing_payload["quantity"] = requested_qty
                existing_payload["qty"] = requested_qty
            else:
                services.append(
                    self._entry_service_payload(
                        service=service,
                        quantity=requested_qty,
                        unit_price=unit_price,
                    )
                )
            entry.services = services
            # R-41 fix: flag_modified для JSON column — без этого SQLAlchemy
            # не обнаруживает изменение mutable JSON field, update не persist'ится.
            # Silent data loss: пользователь меняет услуги, но БД не обновляется.
            attributes.flag_modified(entry, 'services')
            entry.service_codes = self._merged_service_codes(entry.service_codes, service)
            attributes.flag_modified(entry, 'service_codes')
            entry.total_amount = int(Decimal(str(entry.total_amount or 0)) + delta_amount)
            entry.updated_at = changed_at

        visit = self._ensure_entry_visit(
            entry=entry,
            patient=patient,
            service=service,
            target_date=target_date,
            specialist_id=specialist_id,
            discount_mode=discount_mode,
            current_user=current_user,
            create_only_if_needed=delta_qty != 0,
        )

        if visit and delta_qty != 0:
            visit.updated_at = changed_at
            self._sync_visit_service_quantity(
                visit=visit,
                service=service,
                requested_qty=requested_qty,
                delta_qty=delta_qty,
                unit_price=row_unit_price,
            )

        return self._delta_result(
            entry=entry,
            service=service,
            visit=visit,
            delta_qty=delta_qty,
            unit_price=unit_price,
            delta_amount=delta_amount,
        )

    def _create_new_queue_entry(
        self,
        *,
        patient: Patient,
        service: Service,
        requested_qty: int,
        target_date: date,
        specialist_id: int | None,
        discount_mode: str,
        all_free: bool,
        current_user: User | None,
    ) -> dict[str, Any]:
        queue_tag = service.queue_tag or service.department_key
        daily_queue = self._resolve_daily_queue(
            service=service,
            specialist_id=specialist_id,
            queue_tag=queue_tag,
            target_date=target_date,
        )
        unit_price = Decimal("0") if all_free else Decimal(str(service.price or 0))
        delta_amount = unit_price * Decimal(requested_qty)
        visit = self._create_visit(
            patient=patient,
            service=service,
            target_date=target_date,
            specialist_id=specialist_id or daily_queue.specialist_id,
            discount_mode=discount_mode,
            current_user=current_user,
        )
        self._sync_visit_service_quantity(
            visit=visit,
            service=service,
            requested_qty=requested_qty,
            delta_qty=requested_qty,
            unit_price=unit_price,
        )
        entry = queue_service.create_queue_entry(
            self.db,
            daily_queue=daily_queue,
            patient_id=patient.id,
            patient_name=patient.short_name(),
            phone=patient.phone,
            visit_id=visit.id,
            source="desk",
            status="waiting",
            services=[
                self._entry_service_payload(
                    service=service,
                    quantity=requested_qty,
                    unit_price=unit_price,
                )
            ],
            service_codes=self._merged_service_codes([], service),
            total_amount=int(delta_amount),
            auto_number=True,
            commit=False,
        )
        entry.updated_at = queue_service.get_local_timestamp(self.db)
        return self._delta_result(
            entry=entry,
            service=service,
            visit=visit,
            delta_qty=requested_qty,
            unit_price=unit_price,
            delta_amount=delta_amount,
        )

    def _ensure_entry_visit(
        self,
        *,
        entry: OnlineQueueEntry,
        patient: Patient,
        service: Service,
        target_date: date,
        specialist_id: int | None,
        discount_mode: str,
        current_user: User | None,
        create_only_if_needed: bool,
    ) -> Visit | None:
        if entry.visit_id:
            visit = self.db.query(Visit).filter(Visit.id == entry.visit_id).first()
            if visit:
                if visit.patient_id != patient.id:
                    raise ValueError(
                        "Queue entry visit does not belong to the requested patient"
                    )
                return visit
            if not create_only_if_needed:
                return None
        if not create_only_if_needed:
            return None
        visit = self._create_visit(
            patient=patient,
            service=service,
            target_date=target_date,
            specialist_id=specialist_id or entry.queue.specialist_id,
            discount_mode=discount_mode,
            current_user=current_user,
        )
        entry.visit_id = visit.id
        entry.updated_at = queue_service.get_local_timestamp(self.db)
        return visit

    def _create_visit(
        self,
        *,
        patient: Patient,
        service: Service,
        target_date: date,
        specialist_id: int | None,
        discount_mode: str,
        current_user: User | None,
    ) -> Visit:
        visit = Visit(
            patient_id=patient.id,
            doctor_id=specialist_id,
            visit_date=target_date,
            visit_time=None,
            department=service.department_key or service.queue_tag,
            discount_mode=discount_mode or "none",
            status="open",
            approval_status="approved",
            confirmed_at=datetime.now(UTC),
            confirmed_by=f"registrar_{current_user.id}" if current_user else None,
            source="desk",
        )
        self.db.add(visit)
        self.db.flush()
        return visit

    def _sync_visit_service_quantity(
        self,
        *,
        visit: Visit,
        service: Service,
        requested_qty: int,
        delta_qty: int,
        unit_price: Decimal,
    ) -> None:
        """W2-PR1: целевое состояние позиции VisitService.

        Существующая строка получает АБСОЛЮТНОЕ целевое количество — прежний
        max(current, requested) молча проглатывал уменьшение. Рост приходит
        со средневзвешенной ценой за единицу (Codex R10 #3115 (P1)): старые
        единицы сохраняют записанную стоимость, добавленные биллятся по
        каталогу — итог строки совпадает с invoice; снижение цену не трогает
        (вычитается фактически начисленная сумма)."""
        existing = (
            self.db.query(VisitService)
            .filter(VisitService.visit_id == visit.id, VisitService.service_id == service.id)
            .first()
        )
        code = self._service_code(service)
        if existing:
            existing.qty = requested_qty
            if delta_qty > 0:
                existing.price = unit_price
                existing.code = code
                existing.name = service.name
                existing.currency = service.currency or "UZS"
            visit.updated_at = queue_service.get_local_timestamp(self.db)
            return
        visit.updated_at = queue_service.get_local_timestamp(self.db)
        self.db.add(
            VisitService(
                visit_id=visit.id,
                service_id=service.id,
                code=code,
                name=service.name,
                qty=requested_qty,
                price=unit_price,
                currency=service.currency or "UZS",
            )
        )

    def _resolve_daily_queue(
        self,
        *,
        service: Service,
        specialist_id: int | None,
        queue_tag: str | None,
        target_date: date,
    ) -> DailyQueue:
        # W2-PR2 (ADR-001): очередь принадлежит ВРАЧУ. Если позиция привязана
        # к специалисту — разрешаем очередь ТОЛЬКО через канонический
        # get_or_create_daily_queue (поиск по (day, specialist_id, active),
        # при отсутствии — создание собственной очереди врача). Прежний поиск
        # по (day, queue_tag) с возвратом первой по id очереди повторял
        # до-PR26 антипаттерн: услуга врача B попадала в очередь врача A
        # (или resource-очередь) того же тега — выбранный врач терялся.
        resolved_specialist_id = specialist_id or service.doctor_id
        if resolved_specialist_id is not None:
            return queue_service.get_or_create_daily_queue(
                self.db,
                day=target_date,
                specialist_id=resolved_specialist_id,
                queue_tag=queue_tag,
                defaults={},
            )
        # Услуга без врача (specialist_id не назван и service.doctor_id пуст):
        # легаси-поведение — активная очередь того же тега (в т.ч. owned
        # ресурсом по QD-2A), иначе громкий отказ вместо тихого «первая
        # попавшаяся».
        existing = (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.day == target_date,
                DailyQueue.queue_tag == queue_tag,
                DailyQueue.active.is_(True),
            )
            .order_by(DailyQueue.id.asc())
            .first()
        )
        if existing:
            return existing
        raise ValueError(
            f"No active queue exists for queue_tag={queue_tag}; specialist_id is required"
        )

    def _apply_invoice_delta(
        self,
        *,
        patient_id: int,
        payment_method: str,
        visit_delta_amounts: dict[int, Decimal],
        total_amount: Decimal,
    ) -> PaymentInvoice | None:
        # W2-PR1: дельта стала знаковой — рост доначисляет PENDING-счёт,
        # снижение уменьшает его. Оплаченные счета охраняются guard'ом
        # снижения (_assert_decrease_allowed), возвраты здесь не создаются.
        positives = {
            visit_id: amount
            for visit_id, amount in visit_delta_amounts.items()
            if amount > 0
        }
        negatives = {
            visit_id: amount
            for visit_id, amount in visit_delta_amounts.items()
            if amount < 0
        }
        invoice: PaymentInvoice | None = None
        if positives:
            invoice = self._increase_pending_invoice(
                patient_id=patient_id,
                payment_method=payment_method,
                visit_delta_amounts=positives,
            )
        for visit_id, amount in negatives.items():
            reduced = self._reduce_pending_invoice_for_visit(
                patient_id=patient_id,
                visit_id=visit_id,
                amount=amount,
            )
            if invoice is None:
                invoice = reduced
        return invoice

    def _increase_pending_invoice(
        self,
        *,
        patient_id: int,
        payment_method: str,
        visit_delta_amounts: dict[int, Decimal],
    ) -> PaymentInvoice | None:
        total_amount = sum(visit_delta_amounts.values(), Decimal("0"))
        visit_ids = list(visit_delta_amounts.keys())
        # Кандидат на доначисление ищется БЕЗ блокировки (только чтобы найти
        # id счёта); сама мутация — под FOR UPDATE (см. ниже).
        candidate_link = (
            self.db.query(PaymentInvoiceVisit)
            .join(PaymentInvoice, PaymentInvoice.id == PaymentInvoiceVisit.invoice_id)
            .filter(
                PaymentInvoice.patient_id == patient_id,
                PaymentInvoice.status == "pending",
                PaymentInvoiceVisit.visit_id.in_(visit_ids),
            )
            .order_by(PaymentInvoice.created_at.desc())
            .first()
        )
        if candidate_link is None:
            invoice = PaymentInvoice(
                patient_id=patient_id,
                total_amount=total_amount,
                currency="UZS",
                status="pending",
                payment_method=payment_method or "cash",
                notes="edit-delta",
            )
            self.db.add(invoice)
            self.db.flush()
        else:
            # Codex R11 #3115 (P1, тело ревью): чтение счёта ПОД блокировкой
            # строки + ревалидация статуса в той же транзакции — зеркало
            # R10-фикса снижения. Без этого init_invoice_payment мог
            # заблокировать счёт, отправить провайдеру СТАРУЮ сумму и
            # закоммитить processing, а этот рост доначислял бы
            # total_amount уже обрабатываемому счёту (провайдер соберёт
            # старую сумму, визит/очередь уже содержат рост). Параллельные
            # росты тоже сериализуются: второй видит закоммиченный итог.
            invoice = (
                self.db.query(PaymentInvoice)
                .filter(PaymentInvoice.id == candidate_link.invoice_id)
                .with_for_update()
                .first()
            )
            if invoice is None:
                raise ValueError("Счёт по визиту не найден при доначислении")
            if invoice.status != "pending":
                raise ValueError(
                    f"Счёт по визиту уже обрабатывается (статус {invoice.status}) — "
                    "увеличение количества выполняется через новую позицию или корректировку оплаты"
                )
            invoice.total_amount = Decimal(str(invoice.total_amount or 0)) + total_amount

        for visit_id, visit_amount in visit_delta_amounts.items():
            link = (
                self.db.query(PaymentInvoiceVisit)
                .filter(
                    PaymentInvoiceVisit.invoice_id == invoice.id,
                    PaymentInvoiceVisit.visit_id == visit_id,
                )
                .first()
            )
            if link:
                link.visit_amount = Decimal(str(link.visit_amount or 0)) + visit_amount
            else:
                self.db.add(
                    PaymentInvoiceVisit(
                        invoice_id=invoice.id,
                        visit_id=visit_id,
                        visit_amount=visit_amount,
                    )
                )
        return invoice

    def _reduce_pending_invoice_for_visit(
        self,
        *,
        patient_id: int,
        visit_id: int,
        amount: Decimal,
    ) -> PaymentInvoice | None:
        """W2-PR1: снижение позиции уменьшает PENDING-счёт того же визита.

        amount < 0. Оплаченные счета отвергнуты guard'ом снижения; отсутствие
        pending-счёта означает, что начисление по этой позиции ещё не
        выставлялось — корректировать нечего. Расхождение (сумма позиции
        меньше вычитаемой) — громкий отказ вместо тихой порчи счёта."""
        link = (
            self.db.query(PaymentInvoiceVisit)
            .join(PaymentInvoice, PaymentInvoice.id == PaymentInvoiceVisit.invoice_id)
            .filter(
                PaymentInvoice.patient_id == patient_id,
                PaymentInvoice.status == "pending",
                PaymentInvoiceVisit.visit_id == visit_id,
            )
            .order_by(PaymentInvoice.created_at.desc())
            .first()
        )
        if link is None:
            return None
        # Codex R10 #3115 (P1): чтение счёта ПОД блокировкой строки +
        # повторная валидация статуса в той же транзакции. Без этого гонка
        # с init_invoice_payment (чтение pending → запрос провайдеру на
        # старую сумму → processing) могла пройти мимо guard'а: снижение
        # уменьшало pending-счёт ПОСЛЕ того, как провайдеру ушла старая
        # сумма. FOR UPDATE сериализует обе операции: кто первый взял
        # блокировку, второй видит закоммиченное состояние.
        invoice = (
            self.db.query(PaymentInvoice)
            .filter(PaymentInvoice.id == link.invoice_id)
            .with_for_update()
            .first()
        )
        if invoice is None:
            return None
        if invoice.status != "pending":
            raise ValueError(
                f"Счёт по визиту уже обрабатывается (статус {invoice.status}) — "
                "уменьшение количества выполняется через возврат/корректировку оплаты"
            )
        new_visit_amount = Decimal(str(link.visit_amount or 0)) + amount
        new_total = Decimal(str(invoice.total_amount or 0)) + amount
        if new_visit_amount < 0 or new_total < 0:
            raise ValueError(
                "Нельзя уменьшить сумму позиции ниже выставленной по счёту. "
                "Обновите данные записи и повторите попытку"
            )
        link.visit_amount = new_visit_amount
        invoice.total_amount = new_total
        return invoice

    def _delta_result(
        self,
        *,
        entry: OnlineQueueEntry,
        service: Service,
        visit: Visit | None,
        delta_qty: int,
        unit_price: Decimal,
        delta_amount: Decimal,
    ) -> dict[str, Any]:
        return {
            "queue_entry_id": entry.id,
            "queue_id": entry.queue_id,
            "number": entry.number,
            "queue_status": entry.status,
            "visit_id": visit.id if visit else entry.visit_id,
            "doctor_id": visit.doctor_id if visit else None,
            "service_id": service.id,
            "delta_quantity": delta_qty,
            "unit_price": unit_price,
            "delta_amount": delta_amount,
        }

    def _coerce_services(self, services_value: Any) -> list[dict[str, Any]]:
        if not services_value:
            return []
        if isinstance(services_value, list):
            return [
                dict(item) if isinstance(item, dict) else {"name": str(item)}
                for item in services_value
            ]
        if isinstance(services_value, str):
            try:
                parsed = json.loads(services_value)
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
                if isinstance(parsed, list):
                    return [
                        dict(item) if isinstance(item, dict) else {"name": str(item)}
                        for item in parsed
                    ]
            except Exception:
                return []
        return []

    def _find_service_payload(
        self, services: list[dict[str, Any]], service: Service
    ) -> dict[str, Any] | None:
        target_code = self._service_code(service)
        for payload in services:
            payload_id = payload.get("service_id") or payload.get("id")
            payload_code = payload.get("code") or payload.get("service_code")
            if payload_id == service.id:
                return payload
            if target_code and payload_code and normalize_service_code(payload_code) == target_code:
                return payload
        return None

    def _recorded_unit_charge(
        self,
        *,
        entry: OnlineQueueEntry,
        payload: dict[str, Any],
        previous_qty: int,
    ) -> Decimal:
        """Codex R8 #3115 (P1): фактически ЗАПИСАННАЯ цена за единицу позиции.

        Конвенции записчиков payload различаются: full-update сохраняет в
        price ПОЛНУЮ сумму строки (unit × quantity), а desk/edit-delta —
        цену за единицу. Умножение «цены из payload» на дельту для
        full-update-строки списывало бы line-total повторно (снижение
        3→1 при 100/усл. вычитало бы 600 вместо 200).

        Правило вывода:
        1) явный payload["unit_price"] — канонический источник (новые строки);
        2) quantity <= 1 — конвенции совпадают, price и есть цена за единицу;
        3) по сумме записи: total_amount == Σ price (line-total конвенция,
           как у full-update) И != Σ price×qty → цена за единицу = price/qty;
        4) иначе — unit-конвенция: price (desk/edit-delta строки).
        """
        raw_price = payload.get("price")
        if raw_price is None:
            return Decimal("0")
        price = Decimal(str(raw_price))
        if "unit_price" in payload and payload.get("unit_price") is not None:
            return Decimal(str(payload["unit_price"]))
        if previous_qty <= 1:
            return price
        services = self._coerce_services(entry.services)
        line_sum = sum(
            (Decimal(str(p.get("price") or 0)) for p in services), Decimal("0")
        )
        unit_sum = sum(
            (
                Decimal(str(p.get("price") or 0)) * Decimal(int(self._payload_quantity(p) or 1))
                for p in services
            ),
            Decimal("0"),
        )
        total = Decimal(str(entry.total_amount or 0))
        if total == line_sum and line_sum != unit_sum:
            return price / Decimal(previous_qty)
        return price

    def _payload_quantity(self, payload: dict[str, Any] | None) -> int:
        if not payload:
            return 0
        try:
            return max(int(payload.get("quantity") or payload.get("qty") or 1), 1)
        except (TypeError, ValueError):
            return 1

    def _entry_service_payload(
        self,
        *,
        service: Service,
        quantity: int,
        unit_price: Decimal,
    ) -> dict[str, Any]:
        code = self._service_code(service)
        return {
            "id": service.id,
            "service_id": service.id,
            "code": code,
            "service_code": code,
            "name": service.name,
            "service_name": service.name,
            "quantity": quantity,
            "qty": quantity,
            "price": float(unit_price),
            # Codex R8 #3115 (P1): явная цена за единицу — payload-поле price
            # в разных записчиках означает разное (unit или line-total);
            # это поле снимает неоднозначность для будущих правок снижения.
            "unit_price": float(unit_price),
        }

    def _service_response_payload(
        self,
        *,
        service: Service,
        quantity: int,
        price: Decimal,
    ) -> dict[str, Any]:
        code = self._service_code(service)
        return {
            "name": service.name,
            "code": code,
            "quantity": quantity,
            "price": float(price),
        }

    def _merged_service_codes(self, existing_codes: Any, service: Service) -> list[str]:
        codes: list[str] = []
        if isinstance(existing_codes, list):
            codes.extend(str(code) for code in existing_codes if code)
        elif isinstance(existing_codes, str):
            try:
                parsed = json.loads(existing_codes)
                if isinstance(parsed, list):
                    codes.extend(str(code) for code in parsed if code)
            except Exception:
                if existing_codes:
                    codes.append(existing_codes)
        code = self._service_code(service)
        if code:
            codes.append(code)
        deduped: list[str] = []
        seen: set[str] = set()
        for code_value in codes:
            normalized = normalize_service_code(code_value)
            if normalized and normalized not in seen:
                deduped.append(normalized)
                seen.add(normalized)
        return deduped

    def _service_code(self, service: Service) -> str | None:
        raw = service.service_code or service.code or get_service_code(service.id, self.db)
        return normalize_service_code(raw) if raw else None

    def _doctor_name(self, doctor_id: int | None) -> str:
        if not doctor_id:
            return "Без врача"
        doctor = self.db.query(Doctor).filter(Doctor.id == doctor_id).first()
        if not doctor:
            return "Без врача"
        user = getattr(doctor, "user", None)
        if user:
            return user.full_name or user.username or "Без врача"
        return str(doctor.specialty or "Без врача")
