"""Service layer for legacy queue endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.crud import queue_resource_routing
from app.repositories.queue_api_repository import QueueApiRepository


@dataclass
class QueueApiDomainError(Exception):
    status_code: int
    detail: str


class QueueApiService:
    """Handles endpoint-level DB actions for legacy queue module."""

    def __init__(
        self,
        db: Session,
        repository: QueueApiRepository | None = None,
    ):
        self.repository = repository or QueueApiRepository(db)

    def get_doctor_user(self, specialist_id: int):
        return self.repository.get_doctor_user(specialist_id)

    def get_daily_queue(self, *, day: date, specialist_id: int):
        """QD-2C (Codex round-6 P1): the registry surface first — the
        legacy open/close/today/statistics endpoints must all address
        the ONE (day, tag) surface the switched runtime uses, not a
        parallel doctor-owned shadow. Pure lookup (no creation); a
        doctor queue without a registry surface keeps the raw
        doctor-keyed lookup."""
        surface = queue_resource_routing.resolve_registry_tag_queue_for_specialist(
            self.repository.db, day, specialist_id, None
        )
        if surface is not None:
            return surface
        return self.repository.get_daily_queue(day=day, specialist_id=specialist_id)

    def get_or_create_daily_queue(self, *, day: date, specialist_id: int):
        """QD-2C (Codex round-6 P1): registry-tag specialists (the
        synthetic lab/ecg Doctors) get the (day, tag) surface returned
        or created as a resource-owned queue — the legacy/open flow
        must not fork an active untagged doctor row next to the live
        resource queue. Tags without a registry row keep the legacy
        doctor-keyed path byte-identically."""
        doctor = self.repository.get_doctor(specialist_id)
        if doctor is not None and doctor.specialty:
            registry_queue = self.repository.get_or_create_registry_queue(
                day=day, queue_tag=doctor.specialty
            )
            if registry_queue is not None:
                return registry_queue
        # Lock-parity follow-up to the #3511 review (merge-gate P1): the
        # legacy ``POST /queue/open`` doctor path is the FIFTH creator
        # of a doctor's day queue — serialize its check-then-insert on
        # the canonical (day, doctor) advisory key, the same scope
        # queue_service.get_or_create_daily_queue holds. A canonical
        # writer (registrar cart, morning assignment) racing this
        # deprecated-but-mounted endpoint for the same (day, doctor)
        # could both observe no queue and insert: two NULL-tag rows fail
        # the loser on ``uq_daily_queues_active_doctor_day_tag`` with an
        # unhandled IntegrityError, and a tagged-vs-NULL-tag pair — the
        # partial unique's COALESCE(queue_tag, '') keys differ — forks
        # TWO active queues for one doctor-day. Taken BEFORE the lookup;
        # create_daily_queue's commit releases the transaction-scoped
        # lock. Advisory-first: nothing row-locked earlier in this flow
        # (the registry branch exits on plain lookups or returns a
        # queue; its deactivation-race tag lock precedes this in the
        # same tag-then-doctor order the canonical batch flow uses).
        # PostgreSQL-only; the sequential SQLite tests skip harmlessly.
        queue_resource_routing.lock_daily_queue_creation(
            self.repository.db, day, specialist_id
        )
        daily_queue = self.repository.get_daily_queue(
            day=day, specialist_id=specialist_id
        )
        if daily_queue:
            return daily_queue
        return self.repository.create_daily_queue(day=day, specialist_id=specialist_id)

    def open_daily_queue(self, daily_queue) -> None:
        self.repository.set_opened_at_now(daily_queue)

    # UX Audit Registrar #7: close_daily_queue — закрытие приёма (reopen online booking).
    def close_daily_queue(self, daily_queue) -> None:
        self.repository.set_opened_at_none(daily_queue)

    def get_doctor(self, specialist_id: int):
        return self.repository.get_doctor(specialist_id)

    def list_queue_entries(self, *, queue_id: int):
        return self.repository.list_queue_entries(queue_id=queue_id)

    def get_queue_entry(self, entry_id: int):
        return self.repository.get_queue_entry(entry_id)

    def mark_entry_called(
        self, entry, *, called_by_user_id: int | None = None
    ) -> None:
        self.repository.mark_entry_called(
            entry, called_by_user_id=called_by_user_id
        )
