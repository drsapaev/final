"""Service layer for force majeure endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.crud.clinic import clinic_today
from app.crud.queue_resource_routing import (
    resolve_registry_tag_queue_for_specialist,
)
from app.models.online_queue import DailyQueue
from app.models.refund_deposit import (
    DepositTransaction,
    DepositTransactionType,
    PatientDeposit,
    RefundRequestStatus,
    RefundType,
)
from app.repositories.force_majeure_api_repository import ForceMajeureApiRepository
from app.services.force_majeure_service import get_force_majeure_service


@dataclass
class ForceMajeureApiDomainError(Exception):
    status_code: int
    detail: str


class ForceMajeureApiService:
    """Coordinates force majeure domain service and endpoint payload logic."""

    def __init__(
        self,
        db: Session,
        repository: ForceMajeureApiRepository | None = None,
    ):
        self.repository = repository or ForceMajeureApiRepository(db)

    def _validated_daily_queue(
        self,
        *,
        daily_queue_id: int,
        specialist_id: int,
        queue_day: date,
        lock: bool = False,
    ) -> DailyQueue:
        """3808 review round 2 (P1 queue identity): validate the row's
        canonical DailyQueue as the ONLY operation target.

        The queue must exist, belong to the resolved day, and be addressable
        by the specialist (their own queue or their registry tag surface).
        A doctor-owned row must never silently operate the shadow resource
        queue that ``resolve_registry_tag_queue_for_specialist`` would pick.

        3808 review round 3 (P1 concurrent refund): with ``lock=True`` the
        queue row is taken FOR UPDATE BEFORE the entry set is read — every
        force-majeure mutation on this queue serializes on this one row, so
        the loser of a concurrent pair re-reads committed state after the
        winner commits and refuses on drift instead of double-refunding.
        The locked fetch goes through the repository (boundary:
        test_service_repository_boundary forbids direct session calls
        here); SQLite (unit tests) ignores FOR UPDATE.
        """
        if lock:
            queue = self.repository.get_daily_queue_for_update(daily_queue_id)
        else:
            queue = self.repository.db.get(DailyQueue, daily_queue_id)
        if queue is None:
            raise ForceMajeureApiDomainError(404, "Очередь не найдена")
        if queue.day != queue_day:
            raise ForceMajeureApiDomainError(
                422,
                "Очередь принадлежит другому дню",
            )
        if queue.specialist_id != specialist_id:
            surface = resolve_registry_tag_queue_for_specialist(
                self.repository.db, queue.day, specialist_id, None
            )
            if surface is None or surface.id != daily_queue_id:
                raise ForceMajeureApiDomainError(
                    422,
                    "Очередь не принадлежит указанному специалисту",
                )
        return queue

    @staticmethod
    def _validate_selector_contract(
        *,
        daily_queue_id: int | None,
        entry_ids: list[int] | None,
        expected_entry_ids: list[int] | None,
    ) -> None:
        """3808 review round 3 (P1 preview set binding): the request-shape
        contract shared by both mutations.

        * ``entry_ids`` (legacy explicit set) and ``daily_queue_id``
          (canonical row queue) stay mutually exclusive — round 2 rule;
        * ``expected_entry_ids`` is the PREVIEW SNAPSHOT: it only ever
          pairs with ``daily_queue_id`` and is REQUIRED there — without
          it a bound mutation would re-select the whole live queue and
          could touch patients the registrar never saw in the preview
          (the exact round 3 P1);
        * a daily_queue_id mutation with an EMPTY snapshot is a missing
          preview, not an empty-queue operation.
        """
        if daily_queue_id is not None and entry_ids:
            raise ForceMajeureApiDomainError(
                422,
                "daily_queue_id и entry_ids взаимоисключающие: укажите одно",
            )
        if expected_entry_ids and entry_ids:
            raise ForceMajeureApiDomainError(
                422,
                "entry_ids и expected_entry_ids взаимоисключающие: укажите одно",
            )
        if expected_entry_ids and daily_queue_id is None:
            raise ForceMajeureApiDomainError(
                422,
                "expected_entry_ids применим только вместе с daily_queue_id",
            )
        if daily_queue_id is not None and not expected_entry_ids:
            raise ForceMajeureApiDomainError(
                422,
                "daily_queue_id требует expected_entry_ids — снимок ID записей "
                "из предпросмотра (повторите предпросмотр и передайте его результат)",
            )

    def _bound_pending_entries(
        self,
        *,
        queue: DailyQueue,
        expected_entry_ids: list[int] | None,
        service,
    ) -> list[Any]:
        """3808 review round 3 (P1 preview set binding): the mutation must
        touch EXACTLY the entries the registrar saw in the preview.

        The current live pending set of the locked queue is compared to the
        previewed snapshot: ANY drift (a patient added after the preview, or
        a previewed entry gone) refuses with 409 — the registrar must
        re-preview and re-confirm the NEW set. Callers hold the queue row
        lock, so the comparison is race-free for force-majeure writers.
        """
        expected = {int(entry_id) for entry_id in (expected_entry_ids or [])}
        entries = service.get_pending_entries(
            queue_id=queue.id,
            target_date=queue.day,
        )
        current = {entry.id for entry in entries}
        if expected != current:
            added = len(current - expected)
            removed = len(expected - current)
            raise ForceMajeureApiDomainError(
                409,
                "Состав очереди изменился после предпросмотра "
                f"(добавилось: {added}, исчезло: {removed}). "
                "Обновите предпросмотр и подтвердите новый состав",
            )
        return entries

    def transfer_queue_to_tomorrow(self, *, request, current_user_id: int) -> dict[str, Any]:
        service = get_force_majeure_service(self.repository.db)
        # 3808 review round 3 (P1 preview set binding): request-shape
        # contract first (selector exclusivity + snapshot requirement).
        self._validate_selector_contract(
            daily_queue_id=request.daily_queue_id,
            entry_ids=request.entry_ids,
            expected_entry_ids=getattr(request, "expected_entry_ids", None),
        )
        # 3808 review round 2 (P1 transfer destination): the transfer day
        # chain is derived from the SOURCE queue day (request.target_date or
        # the clinic SSOT day) — the same day the entries are selected from.
        queue_day = request.target_date or clinic_today(self.repository.db)
        if request.daily_queue_id is not None:
            queue = self._validated_daily_queue(
                daily_queue_id=request.daily_queue_id,
                specialist_id=request.specialist_id,
                queue_day=queue_day,
                lock=True,
            )
            entries = self._bound_pending_entries(
                queue=queue,
                expected_entry_ids=getattr(request, "expected_entry_ids", None),
                service=service,
            )
        elif request.entry_ids:
            entries = self.repository.list_pending_entries_by_ids(
                request.entry_ids,
                specialist_id=request.specialist_id,
                target_date=request.target_date,
            )
        else:
            entries = service.get_pending_entries(
                specialist_id=request.specialist_id,
                target_date=request.target_date,
            )

        if not entries:
            return {"success": True, "transferred": 0, "message": "Нет записей для переноса"}

        return service.transfer_entries_to_tomorrow(
            entries=entries,
            specialist_id=request.specialist_id,
            reason=request.reason,
            performed_by_id=current_user_id,
            send_notifications=request.send_notifications,
            source_date=queue_day,
        )

    def cancel_queue_with_refund(self, *, request, current_user_id: int) -> dict[str, Any]:
        service = get_force_majeure_service(self.repository.db)
        try:
            refund_type = RefundType(request.refund_type)
        except ValueError as exc:
            raise ForceMajeureApiDomainError(
                400,
                f"Неверный тип возврата: {request.refund_type}",
            ) from exc

        # 3808 review round 3 (P1 preview set binding): request-shape
        # contract first (selector exclusivity + snapshot requirement).
        self._validate_selector_contract(
            daily_queue_id=request.daily_queue_id,
            entry_ids=request.entry_ids,
            expected_entry_ids=getattr(request, "expected_entry_ids", None),
        )
        queue_day = request.target_date or clinic_today(self.repository.db)
        if request.daily_queue_id is not None:
            queue = self._validated_daily_queue(
                daily_queue_id=request.daily_queue_id,
                specialist_id=request.specialist_id,
                queue_day=queue_day,
                lock=True,
            )
            entries = self._bound_pending_entries(
                queue=queue,
                expected_entry_ids=getattr(request, "expected_entry_ids", None),
                service=service,
            )
        elif request.entry_ids:
            entries = self.repository.list_pending_entries_by_ids(
                request.entry_ids,
                specialist_id=request.specialist_id,
                target_date=request.target_date,
            )
        else:
            entries = service.get_pending_entries(
                specialist_id=request.specialist_id,
                target_date=request.target_date,
            )

        if not entries:
            return {"success": True, "cancelled": 0, "message": "Нет записей для отмены"}

        # 3808 review round 4 (P1 cross-channel): единый refund-claim
        # (0088) сериализует возврат одного платежа между конкурентными
        # отменами РАЗНЫХ очередей. В патологическом случае (одни и те же
        # платежи в двух очередях в противоположном порядке обработки)
        # PostgreSQL разрешает взаимоблокировку сам, отменяя одну из
        # транзакций (40P01; сюда же — failure сериализации 40001).
        # Переводим это в 409 с подсказкой повторить, а не в 500: инвариант
        # «один возврат на платеж» не нарушен, повтор подтверждения
        # добьётся already_refunded.
        try:
            return service.cancel_entries_with_refund(
                entries=entries,
                reason=request.reason,
                refund_type=refund_type,
                performed_by_id=current_user_id,
                send_notifications=request.send_notifications,
            )
        except OperationalError as exc:
            if getattr(exc.orig, "pgcode", None) in {"40P01", "40001"}:
                raise ForceMajeureApiDomainError(
                    409,
                    "Конфликт параллельных возвратов одного платежа — "
                    "повторите подтверждение отмены",
                ) from exc
            raise

    def get_pending_entries(
        self,
        *,
        specialist_id: int,
        target_date,
        daily_queue_id: int | None = None,
    ) -> list[dict[str, Any]]:
        service = get_force_majeure_service(self.repository.db)
        if daily_queue_id is not None:
            queue_day = target_date or clinic_today(self.repository.db)
            queue = self._validated_daily_queue(
                daily_queue_id=daily_queue_id,
                specialist_id=specialist_id,
                queue_day=queue_day,
            )
            entries = service.get_pending_entries(
                queue_id=queue.id,
                target_date=queue.day,
            )
        else:
            entries = service.get_pending_entries(
                specialist_id=specialist_id,
                target_date=target_date,
            )
        return [
            {
                "id": entry.id,
                "number": entry.number,
                "patient_name": entry.patient_name,
                "phone": entry.phone,
                "status": entry.status,
                "services": entry.services,
                "total_amount": entry.total_amount,
                "queue_time": entry.queue_time.isoformat() if entry.queue_time else None,
            }
            for entry in entries
        ]

    @staticmethod
    def _patient_short_name(patient) -> str | None:
        if not patient:
            return None
        return patient.short_name() if hasattr(patient, "short_name") else None

    def get_refund_requests(
        self,
        *,
        status_filter: str | None,
        patient_id: int | None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        requests = self.repository.list_refund_requests(
            status_filter=status_filter,
            patient_id=patient_id,
            limit=limit,
            offset=offset,
        )
        return [self._serialize_refund_request(item) for item in requests]

    def get_refund_request(self, *, request_id: int) -> dict[str, Any]:
        req = self.repository.get_refund_request(request_id)
        if not req:
            raise ForceMajeureApiDomainError(404, "Заявка на возврат не найдена")
        return self._serialize_refund_request(req)

    def process_refund_request(
        self,
        *,
        request_id: int,
        process_request,
        current_user,
    ) -> dict[str, Any]:
        # 3808 review round 6 (P1 reject/complete race): заявка читается с
        # блокировкой строки (SELECT ... FOR UPDATE) ДО проверки статуса.
        # ``reject`` и ``complete`` принимают один и тот же исходный
        # ``approved``: без блокировки две кассирские сессии одновременно
        # читают approved, первая отклоняет и освобождает claim, вторая
        # завершает возврат по устаревшей копии — выплаченный возврат
        # теряет защиту от повторного. Сериализация на строке заявки даёт
        # проигравшей сессии свежий статус (READ COMMITTED +
        # populate_existing) и доменный отказ вместо второго перехода;
        # claim при этом остаётся у completed и освобождается только у
        # rejected (см. ветку reject ниже).
        req = self.repository.get_refund_request_for_update(request_id)
        if not req:
            raise ForceMajeureApiDomainError(404, "Заявка на возврат не найдена")

        action = process_request.action.lower()
        if action == "approve":
            if req.status != RefundRequestStatus.PENDING.value:
                raise ForceMajeureApiDomainError(
                    400,
                    "Можно одобрить только заявки со статусом pending",
                )
            req.status = RefundRequestStatus.APPROVED.value
        elif action == "reject":
            if req.status not in [
                RefundRequestStatus.PENDING.value,
                RefundRequestStatus.APPROVED.value,
            ]:
                raise ForceMajeureApiDomainError(
                    400,
                    "Нельзя отклонить заявку с текущим статусом",
                )
            if not process_request.rejection_reason:
                raise ForceMajeureApiDomainError(400, "Укажите причину отклонения")
            req.status = RefundRequestStatus.REJECTED.value
            req.rejection_reason = process_request.rejection_reason
            # 3808 review round 5 (P1 claim lifecycle): reject — терминальный
            # НЕ-платящий статус: деньги пациенту не ушли, поэтому единый
            # claim платежа освобождается В ЭТОЙ ЖЕ транзакции (commit ниже),
            # и повторный возврат — исправленная заявка или депозит —
            # становится возможен. Удаляется только claim этой заявки;
            # claim более поздней заявки не затрагивается. Ленивое
            # самоисцеление в ForceMajeureService._claim_payment_refund
            # покрывает пути отклонения в обход этого метода.
            self.repository.release_refund_claim_for_request(req.id)
        elif action == "complete":
            if req.status != RefundRequestStatus.APPROVED.value:
                raise ForceMajeureApiDomainError(
                    400,
                    "Можно завершить только одобренные заявки",
                )
            req.status = RefundRequestStatus.COMPLETED.value
        else:
            raise ForceMajeureApiDomainError(400, f"Неизвестное действие: {action}")

        req.processed_by = current_user.id
        req.processed_at = datetime.now(UTC)
        if process_request.bank_card_number:
            req.bank_card_number = process_request.bank_card_number
        if process_request.manager_notes:
            req.manager_notes = process_request.manager_notes

        self.repository.commit()
        self.repository.refresh(req)
        payload = self._serialize_refund_request(req)
        payload["processed_by_name"] = current_user.full_name
        return payload

    @staticmethod
    def _refund_request_available_actions(status: str | None) -> list[str]:
        normalized_status = (status or "").strip().lower()
        if normalized_status == RefundRequestStatus.PENDING.value:
            return ["approve", "reject"]
        if normalized_status == RefundRequestStatus.APPROVED.value:
            return ["reject", "complete"]
        return []

    def get_deposits(
        self,
        *,
        active_only: bool,
        min_balance: float | None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        deposits = self.repository.list_deposits(
            active_only=active_only,
            min_balance=min_balance,
            limit=limit,
            offset=offset,
        )
        return [self._serialize_deposit(deposit) for deposit in deposits]

    def get_patient_deposit(self, *, patient_id: int) -> dict[str, Any]:
        deposit = self.repository.get_patient_deposit(patient_id=patient_id)
        if not deposit:
            raise ForceMajeureApiDomainError(404, "Депозит пациента не найден")
        return self._serialize_deposit(deposit)

    def get_deposit_transactions(
        self,
        *,
        deposit_id: int,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        transactions = self.repository.list_deposit_transactions(
            deposit_id=deposit_id,
            limit=limit,
            offset=offset,
        )
        return [
            {
                "id": tx.id,
                "deposit_id": tx.deposit_id,
                "transaction_type": tx.transaction_type,
                "amount": float(tx.amount),
                "balance_after": float(tx.balance_after),
                "description": tx.description,
                "created_at": tx.created_at,
            }
            for tx in transactions
        ]

    def add_to_deposit(self, *, request, current_user_id: int) -> dict[str, Any]:
        amount = Decimal(str(request.amount))
        deposit = self.repository.get_patient_deposit(patient_id=request.patient_id)

        if not deposit:
            deposit = PatientDeposit(patient_id=request.patient_id, balance=amount)
            self.repository.add(deposit)
        else:
            deposit.balance += amount

        self.repository.flush()

        transaction = DepositTransaction(
            deposit_id=deposit.id,
            transaction_type=DepositTransactionType.CREDIT.value,
            amount=amount,
            balance_after=deposit.balance,
            description=request.description or "Пополнение депозита",
            performed_by=current_user_id,
        )
        self.repository.add(transaction)
        self.repository.commit()
        self.repository.refresh(deposit)
        return self._serialize_deposit(deposit)

    def use_deposit_for_payment(self, *, request, current_user_id: int) -> dict[str, Any]:
        amount = Decimal(str(request.amount))
        deposit = self.repository.get_patient_deposit(patient_id=request.patient_id)
        if not deposit:
            raise ForceMajeureApiDomainError(404, "Депозит пациента не найден")
        if deposit.balance < amount:
            raise ForceMajeureApiDomainError(
                400,
                f"Недостаточно средств на депозите. Баланс: {deposit.balance}, запрошено: {amount}",
            )
        if not deposit.is_active:
            raise ForceMajeureApiDomainError(400, "Депозит деактивирован")

        if request.visit_id is not None:
            visit = self.repository.get_visit(request.visit_id)
            if not visit:
                raise ForceMajeureApiDomainError(404, "Visit not found")
            if visit.patient_id != request.patient_id:
                raise ForceMajeureApiDomainError(
                    400,
                    "Visit does not belong to deposit patient",
                )

        deposit.balance -= amount
        self.repository.flush()

        transaction = DepositTransaction(
            deposit_id=deposit.id,
            transaction_type=DepositTransactionType.DEBIT.value,
            amount=amount,
            balance_after=deposit.balance,
            description=request.description or "Оплата визита с депозита",
            visit_id=request.visit_id,
            performed_by=current_user_id,
        )
        self.repository.add(transaction)
        self.repository.commit()
        self.repository.refresh(deposit)
        return self._serialize_deposit(deposit)

    def _serialize_refund_request(self, req) -> dict[str, Any]:
        processed_by_name = req.processor.full_name if req.processor else None
        available_actions = self._refund_request_available_actions(req.status)
        return {
            "id": req.id,
            "patient_id": req.patient_id,
            "patient_name": self._patient_short_name(req.patient),
            "payment_id": req.payment_id,
            "original_amount": float(req.original_amount),
            "refund_amount": float(req.refund_amount),
            "commission_amount": float(req.commission_amount),
            "refund_type": req.refund_type,
            "status": req.status,
            "reason": req.reason,
            "is_automatic": req.is_automatic,
            "bank_card_number": req.bank_card_number,
            "created_at": req.created_at,
            "processed_at": req.processed_at,
            "processed_by_name": processed_by_name,
            "available_actions": available_actions,
            "can_approve": "approve" in available_actions,
            "can_reject": "reject" in available_actions,
            "can_complete": "complete" in available_actions,
        }

    def _serialize_deposit(self, deposit) -> dict[str, Any]:
        return {
            "id": deposit.id,
            "patient_id": deposit.patient_id,
            "patient_name": self._patient_short_name(deposit.patient),
            "balance": float(deposit.balance),
            "currency": deposit.currency,
            "is_active": deposit.is_active,
            "created_at": deposit.created_at,
        }

    def rollback(self) -> None:
        self.repository.rollback()
