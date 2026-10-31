"""Repository helpers for force majeure endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.crud.clinic import clinic_today
from app.crud.queue_resource_routing import resolve_registry_tag_queue_for_specialist
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.refund_deposit import (
    DepositTransaction,
    PatientDeposit,
    PaymentRefundClaim,
    RefundRequest,
)
from app.models.visit import Visit


class ForceMajeureApiRepository:
    """Encapsulates ORM operations for force majeure API service."""

    def __init__(self, db: Session):
        self.db = db

    def list_pending_entries_by_ids(
        self,
        entry_ids: list[int],
        *,
        specialist_id: int,
        target_date: date | None,
    ) -> list[OnlineQueueEntry]:
        """QD-2C (Codex round-6 P1): entry-id requests for a registry-tag
        specialist select entries by the tag SURFACE (the resource-owned
        queue has specialist NULL and never matches the doctor filter);
        non-registry specialists keep the doctor-keyed filter."""
        # Codex round-27 P2: опущенная дата — clinic_today SSOT (как в
        # сервисном get_pending_entries после round-26): entry-ids путь
        # иначе искал ВЧЕРАШНЮЮ поверхность клиники в окне 19:00-24:00Z
        # и возвращал ноль затронутых записей при живой очереди.
        queue_day = target_date or clinic_today(self.db)
        surface = resolve_registry_tag_queue_for_specialist(
            self.db, queue_day, specialist_id, None
        )
        owner_filter = (
            OnlineQueueEntry.queue_id == surface.id
            if surface is not None
            else DailyQueue.specialist_id == specialist_id
        )
        return (
            self.db.query(OnlineQueueEntry)
            .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
            .filter(
                OnlineQueueEntry.id.in_(entry_ids),
                OnlineQueueEntry.status.in_(["waiting", "called"]),
                owner_filter,
                DailyQueue.day == queue_day,
            )
            .all()
        )

    def get_daily_queue_for_update(self, daily_queue_id: int) -> DailyQueue | None:
        """3808 review round 3 (P1 concurrent refund): SELECT ... FOR UPDATE
        on the canonical queue row, taken BEFORE the entry set is read —
        every force-majeure mutation on this queue serializes on this one
        row. populate_existing() keeps the session identity map from
        shadowing the locked re-read. SQLite (unit tests) ignores FOR
        UPDATE — the daily-queue creation locks have the same parity.

        Lives in the repository so the API service keeps the
        no-direct-session-calls boundary (test_service_repository_boundary).
        """
        return (
            self.db.query(DailyQueue)
            .filter(DailyQueue.id == daily_queue_id)
            .with_for_update()
            .populate_existing()
            .first()
        )

    def list_refund_requests(
        self,
        *,
        status_filter: str | None,
        patient_id: int | None,
        limit: int,
        offset: int,
    ) -> list[RefundRequest]:
        query = self.db.query(RefundRequest)
        if status_filter:
            query = query.filter(RefundRequest.status == status_filter)
        if patient_id:
            query = query.filter(RefundRequest.patient_id == patient_id)
        return query.order_by(RefundRequest.created_at.desc()).offset(offset).limit(limit).all()

    def get_refund_request(self, request_id: int) -> RefundRequest | None:
        return self.db.query(RefundRequest).filter(RefundRequest.id == request_id).first()

    def get_refund_request_for_update(self, request_id: int) -> RefundRequest | None:
        """3808 review round 6 (P1 reject/complete race): SELECT ... FOR UPDATE
        на строке заявки, взятый ДО проверки статуса и любого перехода.

        ``reject`` и ``complete`` принимают один и тот же исходный статус
        ``approved``, а обычный SELECT читает снапшот READ COMMITTED без
        блокировки: две кассирские сессии одновременно видят ``approved``,
        первая отклоняет и освобождает claim, вторая — завершает возврат по
        устаревшей копии; выплаченный возврат остаётся без защиты от
        повторного. Блокировка строки заявки сериализует переходы: проиграв
        гонку, сессия после коммита победителя перечитывает (READ COMMITTED
        перечитывает кортеж; ``populate_existing()`` не даёт identity map
        подсунуть устаревший объект) и получает доменный отказ вместо
        второго перехода.

        SQLite (unit) игнорирует FOR UPDATE — гонка живёт в gate_d
        (PostgreSQL): см. test_cashier_reject_vs_complete_race_*.

        Lives in the repository so the API service keeps the
        no-direct-session-calls boundary (test_service_repository_boundary).
        """
        return (
            self.db.query(RefundRequest)
            .filter(RefundRequest.id == request_id)
            .with_for_update()
            .populate_existing()
            .first()
        )

    def release_refund_claim_for_request(self, refund_request_id: int) -> bool:
        """3808 review round 5 (P1 claim lifecycle): кассирский ``reject``
        — терминальный НЕ-платящий статус: деньги пациенту не ушли, и
        единый claim платежа (``payment_refund_claims``, миграция 0088)
        должен освободиться в ТОЙ ЖЕ транзакции, что и смена статуса,
        чтобы повторный возврат (исправленная заявка или депозит) стал
        возможен.

        Удаляется ТОЛЬКО claim, связанный с ЭТОЙ заявкой; свежий claim
        более поздней заявки (созданной после отклонения этой) не
        затрагивается. True — claim найден и удалён, False — заявка
        claim-а не держала (ручная заявка или строка до 0088).

        Lives in the repository so the API service keeps the
        no-direct-session-calls boundary (test_service_repository_boundary).
        """
        claim = (
            self.db.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.refund_request_id == refund_request_id)
            .first()
        )
        if claim is None:
            return False
        self.db.delete(claim)
        return True

    def list_deposits(
        self,
        *,
        active_only: bool,
        min_balance: float | None,
        limit: int,
        offset: int,
    ) -> list[PatientDeposit]:
        query = self.db.query(PatientDeposit)
        if active_only:
            query = query.filter(PatientDeposit.is_active.is_(True))
        if min_balance:
            query = query.filter(PatientDeposit.balance >= min_balance)
        return query.order_by(PatientDeposit.balance.desc()).offset(offset).limit(limit).all()

    def get_patient_deposit(self, *, patient_id: int) -> PatientDeposit | None:
        return self.db.query(PatientDeposit).filter(PatientDeposit.patient_id == patient_id).first()

    def get_visit(self, visit_id: int) -> Visit | None:
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def list_deposit_transactions(
        self,
        *,
        deposit_id: int,
        limit: int,
        offset: int,
    ) -> list[DepositTransaction]:
        return (
            self.db.query(DepositTransaction)
            .filter(DepositTransaction.deposit_id == deposit_id)
            .order_by(DepositTransaction.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def add(self, obj) -> None:
        self.db.add(obj)

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def rollback(self) -> None:
        self.db.rollback()
