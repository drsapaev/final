from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.visit import Visit
from app.services.morning_assignment import MorningAssignmentService

logger = logging.getLogger(__name__)


class RegistrarWizardQueueAssignmentService:
    """Wizard-specific seam for same-day queue assignment."""

    def __init__(
        self,
        db: Session,
        *,
        assignment_service_factory: Callable[[Session], MorningAssignmentService]
        | None = None,
    ) -> None:
        self.db = db
        self._assignment_service_factory = (
            assignment_service_factory or (lambda session: MorningAssignmentService(session))
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
                queue_assignments = assignment_service._assign_queues_for_visit(
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
