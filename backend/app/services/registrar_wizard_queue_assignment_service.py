from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.visit import Visit
from app.services.morning_assignment import (
    MorningAssignmentCreateBranchHandoff,
    MorningAssignmentPreparedQueueAssignment,
    MorningAssignmentService,
)
from app.services.queue_domain_service import QueueDomainService
from app.services.visit_lifecycle_service import VisitLifecycleService

logger = logging.getLogger(__name__)


class RegistrarWizardQueueAssignmentService:
    """Wizard-specific seam for same-day queue assignment."""

    def __init__(
        self,
        db: Session,
        *,
        assignment_service_factory: Callable[[Session], MorningAssignmentService]
        | None = None,
        queue_domain_service_factory: Callable[[Session], QueueDomainService]
        | None = None,
        create_entry_allocator: Callable[
            [MorningAssignmentCreateBranchHandoff],
            Any,
        ]
        | None = None,
        lifecycle_service_factory: Callable[[Session], VisitLifecycleService]
        | None = None,
    ) -> None:
        self.db = db
        self._assignment_service_factory = (
            assignment_service_factory or (lambda session: MorningAssignmentService(session))
        )
        self._queue_domain_service_factory = (
            queue_domain_service_factory or (lambda session: QueueDomainService(session))
        )
        self._create_entry_allocator = (
            create_entry_allocator or self._allocate_create_branch_handoff
        )
        self._lifecycle_service_factory = (
            lifecycle_service_factory or (lambda session: VisitLifecycleService(session))
        )

    def assign_same_day_queue_numbers(
        self,
        visits: Sequence[Visit],
        *,
        target_day: date,
        source: str = "desk",
        current_user: Any | None = None,
    ) -> dict[int, list[dict[str, Any]]]:
        """Assign same-day queue numbers to confirmed visits.

        Args:
            visits: Visits to process. Only visits with ``visit_date == target_day``
                and ``status == "confirmed"`` are processed.
            target_day: The day to assign queues for.
            source: Audit source label (e.g. "desk", "morning_assignment").
            current_user: The authenticated admin/registrar requesting the
                assignment. Threaded through to ``activate_confirmed_visit()``
                for audit attribution (Codex P2 fix). None is allowed
                (batch/system context).
        """
        queue_numbers: dict[int, list[dict[str, Any]]] = {}
        assignment_service = self._assignment_service_factory(self.db)

        for visit in visits:
            if visit.visit_date != target_day or visit.status != "confirmed":
                continue

            try:
                queue_assignments = self._assign_same_day_queues_for_visit(
                    assignment_service,
                    visit,
                    target_day,
                    source=source,
                )
                if queue_assignments:
                    # Gate C bypass fix: delegate to VisitLifecycleService
                    # instead of direct visit.status = "open".
                    # This ensures state machine validation, with_for_update()
                    # row lock, and audit logging.
                    # Codex P2 fix: thread current_user through for audit
                    # attribution (otherwise logs say user_id=batch).
                    self._lifecycle_service_factory(self.db).activate_confirmed_visit(
                        visit_id=visit.id,
                        current_user=current_user,
                        commit=False,
                    )
                    queue_numbers[visit.id] = queue_assignments
                    logger.info(
                        "REGISTRATION: Visit %d - assigned %d queue numbers (source=%s)",
                        visit.id,
                        len(queue_assignments),
                        source,
                    )
                else:
                    logger.warning(
                        "REGISTRATION: Visit %d - no queue numbers assigned (source=%s)",
                        visit.id,
                        source,
                    )
            except Exception as exc:
                logger.warning(
                    "REGISTRATION: Queue assignment failed for visit %d (source=%s): %s",
                    visit.id,
                    source,
                    str(exc),
                    exc_info=True,
                )
                continue

        return queue_numbers

    def _assign_same_day_queues_for_visit(
        self,
        assignment_service: MorningAssignmentService,
        visit: Visit,
        target_day: date,
        *,
        source: str,
    ) -> list[dict[str, Any]]:
        """Assign queue entries for all queue_tags of a visit.

        P2-1c (post-merge stabilization): same defect class as P2-1b.
        The original code called self._rollback_session() on per-queue_tag
        failure, which discarded ALL staged work AND left stale dicts in
        queue_assignments. The loop continued, and the visit was activated
        with stale data (non-empty queue_assignments but 0 real DB entries).

        P2-1c fix: queue_assignments is CLEARED on failure and the visit is
        NOT activated (queue_assignments is empty).

        Codex R1 #3092 (P1): a full db.rollback() is incompatible with the
        atomic cart (/registrar/cart + create_visit(commit=False)) — it
        destroyed the flushed-but-uncommitted cart rows, after which the
        endpoint committed an empty transaction and returned 200 with
        phantom visit IDs.

        Codex R1 follow-up (CI repair): a SAVEPOINT protected the cart but
        conflicted with the savepoint-based db_session test fixture
        (P2-1b warned about exactly this), so the mechanism is now a
        COMPENSATING DELETE of this visit's queue entries in the same
        transaction: the cart is never touched, no rollback, no savepoint.

        Contract (consistent with P2-1b):
            Partial queue assignment is intentionally unsupported. On any
            queue-tag assignment failure, all assignments for the current
            visit are discarded and processing stops.
        """
        unique_queue_tags = assignment_service._get_visit_queue_tags(visit)
        if not unique_queue_tags:
            logger.warning("Визит %d: нет queue_tag в услугах", visit.id)
            return []

        queue_assignments: list[dict[str, Any]] = []
        # Codex R3 #3092 (P1): capture the PK while the instance is alive —
        # after a deep full rollback the ORM instance is expired, and every
        # attribute access below must not depend on a refresh that would
        # raise ObjectDeletedError instead of the loud, explicit failure.
        visit_id = visit.id
        # Codex R1 #3092 (P1): предыдущий _rollback_session() делал ПОЛНЫЙ
        # db.rollback() сессии. В атомарной корзине (/registrar/cart с
        # create_visit(commit=False)) визиты/invoice лежат в той же транзакции
        # как flush-нутые, но не закоммиченные строки — полный rollback стирал
        # корзину, после чего endpoint делал db.commit() и возвращал 200 с ID
        # несуществующих визитов.
        # ИСПРАВЛЕНИЕ (CI, пост-Codex-R2): промежуточный вариант с SAVEPOINT
        # (db.begin_nested()) защищал корзину, но несовместим с тестовой
        # инфраструктурой — db_session-фикстура conftest сама строит
        # savepoint-изоляцию (P2-1b прямо предупреждал: «avoids conflicts
        # with test infrastructure that uses begin_nested()»): вложенный
        # session-level savepoint ломал учёт savepoint-ов фикстуры, teardown
        # падал «no such savepoint» и утекал connection — каскад ложных
        # падений всей integration-секции в CI.
        # Итоговый механизм — КОМПЕНСИРУЮЩАЯ зачистка без rollback и без
        # savepoint: при сбое присвоения записи очереди ЭТОГО визита
        # удаляются явным DELETE в той же транзакции. Корзина не затрагивается
        # (её строки даже не перечитываются), контракт P2-1c «после сбоя в БД
        # не остаётся ни одной записи очереди визита» выполняется, частичное
        # присвоение по-прежнему невозможно (queue_assignments.clear() + break).
        for queue_tag in unique_queue_tags:
            try:
                prepared_assignment = assignment_service.prepare_wizard_queue_assignment(
                    visit,
                    queue_tag,
                    target_day,
                    source=source,
                )
                assignment = self._materialize_prepared_assignment(prepared_assignment)
                if assignment:
                    queue_assignments.append(assignment)
            except Exception as exc:
                logger.error(
                    "Ошибка присвоения очередей для визита %d: %s",
                    visit_id,
                    str(exc),
                    exc_info=True,
                )
                # Codex R3 #3092 (P1): belt-and-suspenders. A deep helper that
                # still performs a FULL session rollback (e.g. legacy
                # get_or_create_daily_queue paths outside the savepoint fix)
                # would erase the flushed cart rows from this transaction.
                # The compensating cleanup below is meaningless then, and
                # swallowing the error would let the endpoint commit a 200
                # for phantom visit/invoice IDs. Verify the visit row still
                # exists IN THE TRANSACTION; if not — fail loudly.
                visit_still_in_tx = (
                    self.db.query(Visit.id).filter(Visit.id == visit_id).first()
                    is not None
                )
                if not visit_still_in_tx:
                    raise
                # Компенсирующая зачистка: DELETE записей очереди этого визита
                # в той же транзакции (почему не rollback и не savepoint — см.
                # комментарий выше). Ошибка зачистки НЕ глотается: она уйдёт в
                # top-level assign_same_day_queue_numbers, визит не будет
                # активирован, а endpoint атомарной корзины не закоммитит
                # частичное состояние (P2-1c).
                self._cleanup_visit_queue_entries(visit)
                # P2-1c: CLEAR stale data — компенсированные записи больше не
                # существуют в транзакции, поэтому словари в queue_assignments
                # ссылались бы на несуществующие строки.
                queue_assignments.clear()
                # P2-1c: обработка останавливается на этом визите — частичное
                # присвоение не поддерживается.
                break

        return queue_assignments

    def _cleanup_visit_queue_entries(self, visit: Visit) -> None:
        """Удалить записи очереди ЭТОГО визита в текущей транзакции.

        Компенсирующее действие вместо rollback/savepoint: rollback стёр бы
        flush-нутые строки атомарной корзины (Codex R1 #3092), savepoint
        несовместим с savepoint-изоляцией db_session-фикстуры в тестах
        (P2-1b). DELETE по visit_id затрагивает только записи очереди
        визита — корзина (визиты/invoice) не перечитывается и не меняется.
        """
        from app.models.online_queue import OnlineQueueEntry

        entries = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.visit_id == visit.id
        ).all()
        for entry in entries:
            self.db.delete(entry)
        if entries:
            self.db.flush()
            logger.info(
                "REGISTRATION: компенсирующая зачистка очереди визита %d — удалено записей: %d",
                visit.id,
                len(entries),
            )

    def _materialize_prepared_assignment(
        self,
        prepared_assignment: MorningAssignmentPreparedQueueAssignment | None,
    ) -> dict[str, Any] | None:
        if prepared_assignment is None:
            return None

        if prepared_assignment.assignment is not None:
            return prepared_assignment.assignment

        create_handoff = prepared_assignment.create_handoff
        if create_handoff is None:
            return None

        queue_entry = self._create_entry_allocator(create_handoff)
        return create_handoff.build_assigned_payload(number=queue_entry.number)

    def _allocate_create_branch_handoff(
        self,
        handoff: MorningAssignmentCreateBranchHandoff,
    ) -> Any:
        queue_domain_service = self._queue_domain_service_factory(self.db)
        return queue_domain_service.allocate_ticket(
            allocation_mode="create_entry",
            **handoff.create_entry_kwargs,
        )
