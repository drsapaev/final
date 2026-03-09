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
            queue_domain_service_factory
            or (lambda session: QueueDomainService(session))
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
                    visit.status = "open"
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
                self._rollback_session()

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
