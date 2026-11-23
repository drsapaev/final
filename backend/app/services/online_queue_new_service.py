"""Service layer for online_queue_new endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import false, func, or_, select, update
from sqlalchemy.orm import Session

from app.models.online_queue import OnlineQueueEntry
from app.models.payment import Payment, PaymentVisit
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.provider_attempt import ProviderActiveVisitReservation
from app.models.refund_deposit import DepositTransaction, RefundRequest
from app.models.user import User
from app.models.visit import Visit
from app.repositories.online_queue_new_repository import OnlineQueueNewRepository
from app.repositories.payment_invoice_repository import record_invoice_visit_release
from app.services.encounter_benefit_net import require_no_existing_financial_adjustment
from app.services.encounter_financial_fence import FinancialFenceError
from app.services.money_input import MoneyInputError, parse_money
from app.services.payment_refund_guard import (
    require_visible_checkout_queue,
    require_visible_unpaid_draft_evidence,
    require_visible_visit_payments,
)
from app.services.visit_lifecycle_service import VisitLifecycleService


@dataclass
class OnlineQueueNewDomainError(Exception):
    status_code: int
    detail: str


# W2-PR3: отменить через корзину можно только ещё НЕ потреблённую запись.
# waiting/called — пациент ждёт или уже вызван, но приём не начался.
# in_service/diagnostics — приём идёт (потребление началось); served —
# приём завершён; incomplete/no_show — потребление зафиксировано.
# Отмена потреблённой записи — это корректировка визита (visit lifecycle),
# а не побочный эффект редактирования корзины.
CANCELABLE_ENTRY_STATUSES = ("waiting", "called")

# Codex R14 PR 3121 (P1): терминальные написания статуса отмены. Канонические
# писатели очереди пишут «cancelled» (queue_svc/_helpers.py, force_majeure,
# batch-операции; его же ждёт queue position API и FE-тип QueueEntryStatus);
# каскад отмены визита в visits.py пишет «canceled». Оба принимаются как
# терминал; запись нормализуется к каноническому «cancelled».
TERMINAL_CANCELED_ENTRY_STATUSES = ("canceled", "cancelled")


class OnlineQueueNewService:
    """Orchestrates online queue entry operations for API layer."""

    def __init__(
        self,
        db: Session,
        repository: OnlineQueueNewRepository | None = None,
    ):
        self.db = db
        self.repository = repository or OnlineQueueNewRepository(db)

    def cancel_entry(
        self,
        *,
        entry_id: int,
        current_user: Any = None,
        reason: str | None = None,
    ) -> OnlineQueueEntry:
        """W2-PR3: согласованное удаление/отмена записи очереди.

        Отмена записи — атомарный каскад в ОДНОЙ транзакции (коммит один,
        в конце; любой отказ оставляет состояние прежним):

        1. Запись читается под блокировкой строки (FOR UPDATE) — сериализация
           с параллельными edit-delta и повторными отменами.
        2. Гвард статуса записи: waiting/called отменяемы; повторная отмена —
           идемпотентность С ДОЗАВЕРШЕНИЕМ каскада (ремонт легаси-строк:
           прежняя реализация меняла только entry.status, оставляя открытый
           визит и pending-счёт); потреблённая запись — явный отказ.
        3. Связанный визит (entry.visit_id) отменяется через
           VisitLifecycleService.cancel_visit(commit=False) — стейт-машина
           визита (confirmed/open/in_progress → canceled; closed/completed
           → отказ) и блокировка строки визита переиспользуются, а не
           дублируются.
        4. Финансовый хвост: по визиту ищутся позиции PaymentInvoiceVisit.
           Счёт в processing/paid — отказ (корректировка/возврат — отдельный
           финансовый контракт, зеркало гарда снижения W2-PR1); канонический
           Payment (paid/processing/completed — деньги получены, pending —
           инициализированная провайдерская ссылка) — отказ (зеркала R9/R10
           PR 3115/3118). PENDING-счёт уменьшается на долю визита; если
           позиций больше не осталось — счёт переводится в cancelled.

        Поверхности: эндпоинт POST /online-queue/entries/{id}/cancel
        (мастер записи при удалении карточки из корзины) и registrar
        record-action cancel (record_kind=online_queue) — обе получают
        одинаковую согласованную семантику вместо «тихого» флипа статуса.
        """
        entry = (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id == entry_id)
            .with_for_update()
            .first()
        )
        if not entry:
            raise OnlineQueueNewDomainError(
                status_code=404,
                detail="Запись очереди не найдена",
            )
        if entry.status in TERMINAL_CANCELED_ENTRY_STATUSES:
            # Codex R14 PR 3121 (P1): идемпотентность (двойной клик,
            # параллельные пути мастера) И ремонт легаси-строк. Ранний
            # возврат без сверки оставлял после прежней реализации открытый
            # визит и pending-счёт («тихий» флип статуса), а легаси-написание
            # «cancelled» вообще падало в 409-гард ниже. Повторная отмена
            # дозавершает каскад: отменяет ещё не отменённый визит и
            # высвобождает долю pending-счёта (с теми же финансовыми
            # гардами), затем запись нормализуется к «cancelled».
            if entry.visit_id:
                self._cascade_linked_visit_cancel(
                    entry=entry, current_user=current_user, reason=reason
                )
            entry.status = "cancelled"
            self.db.commit()
            self.db.refresh(entry)
            return entry
        if entry.status not in CANCELABLE_ENTRY_STATUSES:
            raise OnlineQueueNewDomainError(
                status_code=409,
                detail=(
                    f"Запись уже в статусе «{entry.status}» — отмена недоступна. "
                    "Используйте корректировку визита"
                ),
            )

        if entry.visit_id:
            self._cascade_linked_visit_cancel(
                entry=entry, current_user=current_user, reason=reason
            )

        entry.status = "cancelled"
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def stage_unused_grouped_draft(
        self, *, entry: OnlineQueueEntry, performed_by_id: int | None, reason: str,
    ) -> None:
        """Release a draft only while holding the visit and invoice locks."""
        visit_id = entry.visit_id
        if visit_id is None or self._lock_linked_visit(visit_id) is None:
            return
        self._check_cancellation_visibility()
        self.check_pending_invoice_cancellation(visit_id)
        if entry.status not in CANCELABLE_ENTRY_STATUSES:
            return

        drafts = (
            self.db.query(PaymentInvoice)
            .join(PaymentInvoiceVisit, PaymentInvoiceVisit.invoice_id == PaymentInvoice.id)
            .filter(PaymentInvoiceVisit.visit_id == visit_id, PaymentInvoice.status == "pending")
            .order_by(PaymentInvoice.id)
            .with_for_update(of=PaymentInvoice)
            .populate_existing()
            .limit(2)
            .all()
        )
        if not drafts:
            return
        if len(drafts) != 1:
            raise OnlineQueueNewDomainError(409, "Распределение счёта по визиту требует сверки")
        invoice = drafts[0]
        visit_ids = self.db.scalars(
            select(PaymentInvoiceVisit.visit_id).where(PaymentInvoiceVisit.invoice_id == invoice.id)
        ).all()
        if len(visit_ids) < 2 and invoice.registrar_encounter_id_snapshot is None:
            return
        if self._has_issued_checkout(invoice):
            return

        try:
            require_visible_unpaid_draft_evidence(self.db)
        except FinancialFenceError as exc:
            raise OnlineQueueNewDomainError(409, str(exc)) from exc
        used = self.db.query(or_(
            select(Payment.id).where(or_(
                Payment.visit_id.in_(visit_ids),
                Payment.payment_visits.any(PaymentVisit.visit_id.in_(visit_ids)),
            )).exists(),
            select(ProviderActiveVisitReservation.visit_id)
            .where(ProviderActiveVisitReservation.visit_id.in_(visit_ids)).exists(),
            select(DepositTransaction.visit_id).where(DepositTransaction.visit_id.in_(visit_ids)).exists(),
            select(RefundRequest.visit_id).where(RefundRequest.visit_id.in_(visit_ids)).exists(),
            select(OnlineQueueEntry.visit_id).where(
                OnlineQueueEntry.visit_id == visit_id,
                or_(OnlineQueueEntry.diagnostics_started_at.is_not(None), OnlineQueueEntry.served_at.is_not(None)),
            ).exists(),
        )).scalar()
        if used:
            return

        actor = self.db.get(User, performed_by_id) if performed_by_id is not None else None
        if actor is None:
            raise OnlineQueueNewDomainError(409, "Сотрудник для аудита счёта не подтверждён")
        self._cascade_linked_visit_cancel(entry=entry, current_user=actor, reason=reason)

    @staticmethod
    def _has_issued_checkout(invoice: PaymentInvoice) -> bool:
        return any((
            invoice.provider, invoice.provider_payment_id, invoice.provider_transaction_id,
            invoice.payment_url, invoice.provider_data, invoice.paid_at,
        ))

    def _lock_linked_visit(self, visit_id: int | None) -> Visit | None:
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id)
            .with_for_update()
            .populate_existing()
            .first()
        )

    def _check_cancellation_visibility(self) -> None:
        try:
            require_visible_visit_payments(self.db)
            require_visible_checkout_queue(self.db)
        except FinancialFenceError as exc:
            raise OnlineQueueNewDomainError(409, str(exc)) from exc

    def _cascade_linked_visit_cancel(
        self, *, entry: OnlineQueueEntry, current_user: Any, reason: str | None
    ) -> None:
        """Каскад отмены связанного визита + финансового хвоста (staging).

        Codex R13/R14 PR 3121: используется и основным путём отмены, и
        ремонтом легаси-строк на идемпотентной ветке — семантика едина.

        - Codex R13 (P1): визит читается ПОД блокировкой строки жизненного
          цикла С ПРИНУДИТЕЛЬНЫМ перечитыванием (populate_existing):
          и разблокированный пре-чек, и FOR UPDATE внутри cancel_visit
          возвращали уже загруженную SQLAlchemy identity БЕЗ перечитывания
          колонок — визит, параллельно переведённый open → completed/closed,
          всё ещё оценивался как open и перезаписывался в canceled. Одна
          блокировка — одно гарантированно свежее чтение.
        - Codex R14 (P2): легаси/битая строка с visit_id чужого пациента
          отвергается ДО любых жизненного-цикла и финансовых мутаций
          (зеркало гарда владельца в full_update _online_entries.py):
          visit.patient_id обязан совпадать с entry.patient_id.
        - Codex R13 (P1): финансовые гарды выполняются ДО staging перехода —
          отказ (деньги на визите) не оставляет staged-отменённый визит в
          сессии, который закоммитил бы следующий успешный record
          batch-запроса.
        - Codex R13 (P2): легаси-состояние «активная запись + уже отменённый
          визит» тоже сверяет долю счёта — отмена записи не оставляет
          пациента выставленным счётом.
        """
        self.db.flush()
        if self.db.get_bind().dialect.name == "sqlite":
            self.db.execute(update(OnlineQueueEntry).where(false()).values(id=OnlineQueueEntry.id))
        visit = self._lock_linked_visit(entry.visit_id)
        if visit is None:
            return
        if visit.patient_id != entry.patient_id:
            raise OnlineQueueNewDomainError(
                status_code=409,
                detail=(
                    "Связанный визит не принадлежит пациенту записи — "
                    "отмена недоступна, проверьте данные записи"
                ),
            )
        self._check_cancellation_visibility()
        self._assert_visit_has_no_payments(visit)
        self.check_pending_invoice_cancellation(visit.id)
        sibling = self.db.query(OnlineQueueEntry.id).filter(
            OnlineQueueEntry.visit_id == visit.id,
            OnlineQueueEntry.id != entry.id,
            OnlineQueueEntry.status.not_in(TERMINAL_CANCELED_ENTRY_STATUSES),
        ).first()
        if sibling is not None:
            return

        with self.db.begin_nested():
            self._release_pending_invoice_for_visit(visit, current_user=current_user)
            canceled_now = self._stage_linked_visit_cancel(visit, current_user=current_user)
            if canceled_now and reason:
                visit.notes = (visit.notes or "") + f"\nCanceled: {reason}"

    def _stage_linked_visit_cancel(
        self, visit: Visit, *, current_user: Any
    ) -> bool:
        """Отмена связанного визита через SSOT стейт-машину (commit=False).

        Строка визита УЖЕ заблокирована вызывающим (cancel_entry читает её
        под FOR UPDATE) — стейт-машина переиспользует ту же блокировку и
        тот же свежий identity-map объект (перезаблокировка no-op).

        Возвращает True, если переход выполнен ЭТИМ вызовом; False —
        легаси-состояние «визит уже canceled» (переход не нужен, отмена
        записи легитимна, notes не дополняются). Иные отказы стейт-машины
        (closed/completed) конвертируются в доменную ошибку сервиса;
        вызов выполняется ПОСЛЕ финансовых гардов — staged-изменений нет.
        """
        if visit.status == "canceled":
            return False
        try:
            VisitLifecycleService(self.db).cancel_visit(
                visit_id=visit.id,
                current_user=current_user,
                commit=False,
            )
            return True
        except HTTPException as exc:
            detail = exc.detail
            message = (
                detail.get("message") if isinstance(detail, dict) else str(detail)
            )
            raise OnlineQueueNewDomainError(
                status_code=exc.status_code,
                detail=message or "Отмена визита недоступна",
            ) from exc

    def _assert_visit_has_no_payments(self, visit: Visit) -> None:
        """Зеркала гардов W2-PR1 (_assert_decrease_allowed, R9/R10).

        Отмена записи с деньгами — это возврат (отдельный контракт), а не
        побочный эффект редактирования корзины:
        - Payment paid/processing/completed — деньги уже получены/уходят;
        - Payment pending — инициализированный провайдерский платёж с
          фиксированной суммой и ссылкой (Click/PayMe/Kaspi).
        """
        linked_payment = or_(
            Payment.visit_id == visit.id,
            Payment.payment_visits.any(PaymentVisit.visit_id == visit.id),
        )
        payment_taken = (
            self.db.query(Payment.id)
            .filter(linked_payment, Payment.status.in_(("paid", "processing", "completed")))
            .first()
        )
        if payment_taken:
            raise OnlineQueueNewDomainError(
                status_code=409,
                detail=(
                    "По услуге зарегистрирована оплата — отмена записи выполняется "
                    "через возврат/корректировку оплаты"
                ),
            )
        pending_payment = self.db.query(Payment.id).filter(linked_payment, Payment.status == "pending").first()
        reservation = self.db.query(ProviderActiveVisitReservation.visit_id).filter_by(visit_id=visit.id).first()
        if pending_payment or reservation:
            raise OnlineQueueNewDomainError(
                status_code=409,
                detail=(
                    "По услуге создан неоплаченный онлайн-платёж — отмена записи "
                    "недоступна: сначала отмените платёж или завершите оплату"
                ),
            )

    def check_pending_invoice_cancellation(self, visit_id: int) -> None:
        """Hold the draft lock while checking approvals before cancellation."""
        drafts = (
            self.db.query(PaymentInvoice.id, PaymentInvoice.registrar_encounter_id_snapshot)
            .join(PaymentInvoiceVisit, PaymentInvoiceVisit.invoice_id == PaymentInvoice.id)
            .filter(PaymentInvoiceVisit.visit_id == visit_id, PaymentInvoice.status == "pending")
            .order_by(PaymentInvoice.id)
            .with_for_update(of=PaymentInvoice)
            .all()
        )
        for invoice_id, encounter_id in drafts:
            approved_visit = (
                self.db.query(Visit.id)
                .join(PaymentInvoiceVisit, PaymentInvoiceVisit.visit_id == Visit.id)
                .filter(
                    PaymentInvoiceVisit.invoice_id == invoice_id,
                    func.lower(Visit.approval_status) == "approved",
                    func.lower(Visit.discount_mode).in_(("all_free", "benefit")),
                )
                .first()
            )
            if approved_visit is not None:
                raise OnlineQueueNewDomainError(
                    409, "Требуется повторное решение администратора по льготе или бесплатным услугам",
                )
            if encounter_id is not None:
                try:
                    require_no_existing_financial_adjustment(self.db, visit_id)
                except FinancialFenceError as exc:
                    raise OnlineQueueNewDomainError(409, str(exc)) from exc

    def _release_pending_invoice_for_visit(
        self, visit: Visit, *, current_user: Any,
    ) -> None:
        """Финансовый хвост отмены: убрать долю визита из pending-счёта.

        - processing/paid счёт — явный отказ (зеркало W2-PR1);
        - прочие не-pending статусы (failed/cancelled/refunded) — ссылка
          уже не финансово активна, пропускается;
        - pending счёт: total_amount уменьшается на долю визита, позиция
          PaymentInvoiceVisit удаляется; счёт без оставшихся позиций
          переводится в cancelled (исторические суммы сохранены для аудита).
        """
        self._assert_visit_has_no_payments(visit)
        links = (
            self.db.query(PaymentInvoiceVisit)
            .filter(PaymentInvoiceVisit.visit_id == visit.id)
            .all()
        )
        for link in links:
            invoice = (
                self.db.query(PaymentInvoice)
                .filter(PaymentInvoice.id == link.invoice_id)
                .with_for_update()
                .populate_existing()
                .first()
            )
            if invoice is None:
                continue
            if invoice.status == "processing":
                raise OnlineQueueNewDomainError(
                    status_code=409,
                    detail=(
                        "По услуге идёт обработка платежа — отмена записи недоступна, "
                        "дождитесь завершения оплаты или обратитесь в кассу"
                    ),
                )
            if invoice.status == "paid":
                raise OnlineQueueNewDomainError(
                    status_code=409,
                    detail=(
                        "По услуге есть оплаченный счёт — отмена записи выполняется "
                        "через возврат/корректировку оплаты"
                    ),
                )
            if invoice.status != "pending":
                continue
            if self._has_issued_checkout(invoice):
                raise OnlineQueueNewDomainError(409, "Выставленная ссылка на оплату требует сверки")
            allocations = (
                self.db.query(PaymentInvoiceVisit.id, PaymentInvoiceVisit.visit_amount, Visit.patient_id)
                .outerjoin(Visit, Visit.id == PaymentInvoiceVisit.visit_id)
                .filter(PaymentInvoiceVisit.invoice_id == invoice.id)
                .all()
            )
            if any(row.patient_id != invoice.patient_id for row in allocations):
                raise OnlineQueueNewDomainError(409, "Распределение счёта по визиту требует сверки")
            try:
                previous_total = parse_money(invoice.total_amount)
                amounts = {row.id: parse_money(row.visit_amount) for row in allocations}
            except MoneyInputError as exc:
                raise OnlineQueueNewDomainError(409, "Сумма счёта требует сверки") from exc
            if link.id not in amounts or sum(amounts.values(), Decimal("0")) != previous_total:
                raise OnlineQueueNewDomainError(409, "Распределение суммы счёта требует сверки")

            delta = amounts[link.id]
            invoice.total_amount = previous_total - delta
            self.db.delete(link)
            if len(amounts) == 1:
                invoice.status = "cancelled"
            self.db.flush()
            record_invoice_visit_release(
                self.db,
                invoice,
                visit_id=visit.id,
                previous_total=previous_total,
                released_amount=delta,
                actor_user_id=getattr(current_user, "id", None),
                actor_role=getattr(current_user, "role", None),
            )
