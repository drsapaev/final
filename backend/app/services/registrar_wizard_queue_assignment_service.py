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

    def assign_same_day_queue_numbers(
        self,
        visits: Sequence[Visit],
        *,
        target_day: date,
        source: str = "desk",
    ) -> dict[int, list[dict[str, Any]]]:
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
                    VisitLifecycleService(self.db).activate_confirmed_visit(
                        visit_id=visit.id,
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

        Fix: on failure, rollback restores the session, queue_assignments
        is CLEARED to remove stale dicts, and the loop BREAKS. The visit
        is NOT activated (queue_assignments is empty).

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
                    "Ошибка присвоения очереди %s для визита %d: %s",
                    queue_tag,
                    visit.id,
                    str(exc),
                    exc_info=True,
                )
                # P2-1c: rollback to restore the session after failure.
                self._rollback_session()
                # P2-1c: CLEAR stale data. The rollback destroyed all
                # flushed entries, so any dicts in queue_assignments
                # reference non-existent DB rows. Without clearing, the
                # caller would see non-empty queue_assignments and
                # activate the visit with 0 real queue entries.
                queue_assignments.clear()
                # P2-1c: BREAK — after a full rollback, the session state
                # is reset. Continuing the loop would re-query stale data
                # and potentially create partial/inconsistent state.
                break

        return queue_assignments

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

    def _rollback_session(self) -> None:
        rollback = getattr(self.db, "rollback", None)
        if not callable(rollback):
            return

        try:
            rollback()
        except Exception as rollback_error:
            logger.error("Ошибка при rollback wizard queue assignment: %s", rollback_error)
