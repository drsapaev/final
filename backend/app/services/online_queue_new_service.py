"""Service layer for online_queue_new endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.online_queue import OnlineQueueEntry
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.visit import Visit
from app.repositories.online_queue_new_repository import OnlineQueueNewRepository
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
           идемпотентный no-op; потреблённая запись — явный отказ.
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
        if entry.status == "canceled":
            # Идемпотентность: повторная отмена (двойной клик, параллельные
            # пути мастера) — успешный no-op, а не ошибка.
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
            visit = self._cancel_linked_visit(
                entry.visit_id, current_user=current_user
            )
            if visit is not None:
                if reason:
                    visit.notes = (visit.notes or "") + f"\nCanceled: {reason}"
                self._release_pending_invoice_for_visit(visit)

        entry.status = "canceled"
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def _cancel_linked_visit(
        self, visit_id: int, *, current_user: Any
    ) -> Visit | None:
        """Отмена связанного визита через SSOT стейт-машину (commit=False).

        Возвращает None, если визит уже canceled (легаси-состояние
        «запись активна, визит отменён» — каскадировать нечего, отмена
        записи легитимна). Иные отказы стейт-машины (closed/completed)
        конвертируются в доменную ошибку сервиса — транзакция откатывается
        вызывающим контекстом целиком.
        """
        visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
        if visit is not None and visit.status == "canceled":
            return None
        try:
            return VisitLifecycleService(self.db).cancel_visit(
                visit_id=visit_id,
                current_user=current_user,
                commit=False,
            )
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
        payment_taken = (
            self.db.query(Payment)
            .filter(
                Payment.visit_id == visit.id,
                Payment.status.in_(("paid", "processing", "completed")),
            )
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
        pending_payment = (
            self.db.query(Payment)
            .filter(
                Payment.visit_id == visit.id,
                Payment.status == "pending",
            )
            .first()
        )
        if pending_payment:
            raise OnlineQueueNewDomainError(
                status_code=409,
                detail=(
                    "По услуге создан неоплаченный онлайн-платёж — отмена записи "
                    "недоступна: сначала отмените платёж или завершите оплату"
                ),
            )

    def _release_pending_invoice_for_visit(self, visit: Visit) -> None:
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
            delta = Decimal(str(link.visit_amount or 0))
            new_total = Decimal(str(invoice.total_amount or 0)) - delta
            if new_total < 0:
                raise OnlineQueueNewDomainError(
                    status_code=409,
                    detail=(
                        "Нельзя уменьшить сумму счёта ниже выставленной. "
                        "Обновите данные записи и повторите попытку"
                    ),
                )
            remaining_links = (
                self.db.query(PaymentInvoiceVisit)
                .filter(PaymentInvoiceVisit.invoice_id == invoice.id)
                .filter(PaymentInvoiceVisit.id != link.id)
                .count()
            )
            invoice.total_amount = new_total
            self.db.delete(link)
            self.db.flush()
            if remaining_links == 0:
                invoice.status = "cancelled"
