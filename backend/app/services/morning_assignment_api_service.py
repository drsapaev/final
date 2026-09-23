"""Service layer for morning_assignment endpoints."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import OnlineQueueEntry, QueueResource
from app.models.user import User
from app.repositories.morning_assignment_api_repository import (
    MorningAssignmentApiRepository,
)
from app.services.morning_assignment import MorningAssignmentService

# Terminal visit statuses cannot be reactivated by force=true.
# activate_confirmed_visit() is a no-op for these statuses, but
# _assign_queues_for_visit() would have already staged queue entries
# that get committed at end of method — Codex P1 finding.
# pending_confirmation is also non-activatable: activate_confirmed_visit()
# raises HTTP 409, but staged queue entries would still be committed at
# end of method — Codex P1 finding (queue leak). Checked separately
# below to give a distinct error message.
_TERMINAL_STATUSES = frozenset({"closed", "canceled", "expired", "completed"})


class MorningAssignmentApiService:
    """Builds payloads for morning assignment API endpoints."""

    def __init__(
        self,
        db: Session,
        repository: MorningAssignmentApiRepository | None = None,
    ):
        self.repository = repository or MorningAssignmentApiRepository(db)

    def parse_target_date(self, target_date: str | None) -> date:
        # SSOT: дефолт — день КЛИНИКИ по таймзоне очередей (см.
        # visit_confirmation_service._clinic_today), а не host
        # date.today(): на UTC-хосте в окне 19:00-24:00 это уже
        # «вчера» для Asia/Tashkent, и утренняя сборка молча
        # обрабатывает прошедший день.
        from app.crud.clinic import clinic_today

        if not target_date:
            return clinic_today(self.repository.db)
        return datetime.strptime(target_date, "%Y-%m-%d").date()

    def _build_morning_service(self) -> MorningAssignmentService:
        try:
            return MorningAssignmentService(self.repository.db)
        except TypeError:
            # Unit-test compatibility when MorningAssignmentService is monkeypatched
            # with a zero-argument fake implementation.
            service = MorningAssignmentService()
            service.db = self.repository.db
            return service

    def run_assignment_for_date(self, *, target_date: date) -> dict:
        service = self._build_morning_service()
        return service.run_morning_assignment(target_date)

    def get_stats_for_date(self, *, target_date: date) -> dict:
        service = self._build_morning_service()
        return service.get_morning_assignment_stats(target_date)

    def manual_assignment_for_visits(
        self,
        *,
        visit_ids: list[int],
        force: bool,
        current_user: Any | None = None,
    ) -> dict:
        """Manually assign queue numbers to specific visits.

        Args:
            visit_ids: Visits to process.
            force: When True, allow processing of non-standard active statuses
                (e.g. ``in_progress``). Terminal and ``pending_confirmation``
                statuses are ALWAYS rejected regardless of ``force`` — they
                cannot be activated through this path.
            current_user: The authenticated admin/registrar requesting the
                assignment. Threaded through to ``activate_confirmed_visit()``
                for audit attribution. None is allowed (batch/system context).
        """
        service = self._build_morning_service()
        results = []

        for visit_id in visit_ids:
            visit = self.repository.get_visit(visit_id)
            if not visit:
                results.append(
                    {
                        "visit_id": visit_id,
                        "success": False,
                        "message": "Визит не найден",
                    }
                )
                continue

            # Codex P1 fix: reject non-activatable statuses BEFORE staging
            # queue entries. activate_confirmed_visit() is a no-op for
            # terminal statuses and raises 409 for pending_confirmation,
            # but _assign_queues_for_visit() would already have staged
            # entries that the unconditional commit at end of method would
            # persist — silent regression + queue leak.
            if visit.status in _TERMINAL_STATUSES:
                results.append(
                    {
                        "visit_id": visit_id,
                        "success": False,
                        "message": (
                            f"Визит в терминальном статусе '{visit.status}' — "
                            "активация невозможна"
                        ),
                    }
                )
                continue

            if visit.status == "pending_confirmation":
                results.append(
                    {
                        "visit_id": visit_id,
                        "success": False,
                        "message": (
                            "Визит ожидает подтверждения. Активация невозможна "
                            "до подтверждения (используйте confirm_visit)."
                        ),
                    }
                )
                continue

            if visit.status not in ["confirmed", "open"] and not force:
                results.append(
                    {
                        "visit_id": visit_id,
                        "success": False,
                        "message": (
                            f"Визит имеет статус {visit.status}, "
                            "используйте force=true для принудительной обработки"
                        ),
                    }
                )
                continue

            try:
                queue_assignments = service._assign_queues_for_visit(
                    visit,
                    visit.visit_date,
                )
                if queue_assignments:
                    # Gate C bypass fix: delegate to VisitLifecycleService
                    # instead of direct visit.status = "open".
                    # This ensures state machine validation, with_for_update()
                    # row lock, and audit logging.
                    # Codex P2 fix: thread current_user through for audit
                    # attribution (otherwise logs say user_id=batch).
                    #
                    # Codex P1 fix (PR 2721): for visits that are ALREADY
                    # active (open, in_progress, completed), activate_confirmed_visit()
                    # is a no-op (it only transitions confirmed → open). Previously,
                    # the no-op was silently reported as success, which was misleading.
                    # Now we only call activate_confirmed_visit for visits that
                    # actually need activation (status == "confirmed"). For already-
                    # active visits, queue assignment is still legitimate (admin
                    # re-assigning queue numbers), but we report it as "reassignment"
                    # rather than "activation".
                    from app.services.visit_lifecycle_service import (
                        VisitLifecycleService,
                    )

                    if visit.status == "confirmed":
                        VisitLifecycleService(
                            self.repository.db
                        ).activate_confirmed_visit(
                            visit_id=visit.id,
                            current_user=current_user,
                            commit=False,
                        )
                        message = f"Присвоено {len(queue_assignments)} номеров"
                    else:
                        # Already active (open, in_progress, completed) —
                        # queue reassignment without lifecycle transition.
                        # This is the legitimate force=true use case.
                        message = (
                            f"Переназначено {len(queue_assignments)} номеров "
                            f"(визит уже активен: {visit.status})"
                        )

                    results.append(
                        {
                            "visit_id": visit_id,
                            "success": True,
                            "message": message,
                            "queue_assignments": queue_assignments,
                        }
                    )
                else:
                    results.append(
                        {
                            "visit_id": visit_id,
                            "success": False,
                            "message": "Не удалось присвоить номера",
                        }
                    )
            except Exception:  # noqa: BLE001
                results.append(
                    {
                        "visit_id": visit_id,
                        "success": False,
                        "message": "Внутренняя ошибка",
                    }
                )

        self.repository.commit()
        return {
            "success": True,
            "message": f"Обработано {len(visit_ids)} визитов",
            "results": results,
        }

    def get_pending_visits_payload(self, *, target_date: date) -> dict:
        service = self._build_morning_service()
        pending_visits = service._get_confirmed_visits_without_queues(target_date)

        visits_info = []
        for visit in pending_visits:
            patient = self.repository.get_patient(visit.patient_id)
            queue_tags = service._get_visit_queue_tags(visit)
            visits_info.append(
                {
                    "visit_id": visit.id,
                    "patient_id": visit.patient_id,
                    "patient_name": (
                        patient.short_name() if patient else "Неизвестный"
                    ),
                    "visit_date": visit.visit_date.isoformat(),
                    "visit_time": visit.visit_time,
                    "status": visit.status,
                    "confirmed_at": (
                        visit.confirmed_at.isoformat() if visit.confirmed_at else None
                    ),
                    "queue_tags": list(queue_tags),
                    "department": visit.department,
                }
            )

        return {
            "success": True,
            "date": target_date.isoformat(),
            "pending_visits_count": len(pending_visits),
            "pending_visits": visits_info,
        }

    def get_queue_summary_payload(self, *, target_date: date) -> dict:
        queues = self.repository.list_daily_queues(day=target_date)
        lookups = self._load_queue_summary_lookups(queues)
        if lookups is None:
            entry_counts: dict[int, int] = {}
            doctor_names: dict[int, str | None] = {}
            resource_names: dict[int, str] = {}
        else:
            entry_counts, doctor_names, resource_names = lookups

        queue_summary = []

        for queue in queues:
            if lookups is None:
                entries_count = self.repository.count_queue_entries(queue_id=queue.id)
            else:
                entries_count = entry_counts.get(queue.id, 0)
            # QD-2C (Codex round-15 P2): resource-очередь (specialist
            # NULL) — владелец из реестра (display_name), не «ID:None»
            # в админ-сводке; врач-очереди байт-идентичны. getattr:
            # юнит-стабы (SimpleNamespace) — round-8/10 конвенция.
            resource_id = getattr(queue, "queue_resource_id", None)
            if resource_id is not None:
                if lookups is None:
                    resource = getattr(queue, "queue_resource", None)
                    doctor_name = (
                        resource.display_name
                        if resource is not None
                        else "Ресурс очереди"
                    )
                else:
                    doctor_name = resource_names.get(resource_id, "Ресурс очереди")
            else:
                if lookups is None:
                    doctor = self.repository.get_doctor(queue.specialist_id)
                    doctor_name = (
                        doctor.user.full_name
                        if doctor and doctor.user
                        else f"ID:{queue.specialist_id}"
                    )
                else:
                    doctor_name = doctor_names.get(
                        queue.specialist_id, f"ID:{queue.specialist_id}"
                    )
            queue_summary.append(
                {
                    "queue_id": queue.id,
                    "queue_tag": queue.queue_tag or "general",
                    "doctor_name": doctor_name,
                    "doctor_id": queue.specialist_id,
                    "queue_resource_id": resource_id,
                    "entries_count": entries_count,
                    "active": queue.active,
                    "opened_at": (
                        queue.opened_at.isoformat() if queue.opened_at else None
                    ),
                }
            )

        return {
            "success": True,
            "date": target_date.isoformat(),
            "queues_count": len(queues),
            "total_entries": sum(item["entries_count"] for item in queue_summary),
            "queues": queue_summary,
        }

    def _load_queue_summary_lookups(
        self, queues: list[Any]
    ) -> tuple[dict[int, int], dict[int, str | None], dict[int, str]] | None:
        db = getattr(self.repository, "db", None)
        if not callable(getattr(db, "query", None)):
            return None

        queue_ids = [queue.id for queue in queues]
        if not queue_ids:
            return {}, {}, {}

        entry_counts = dict(
            db.query(OnlineQueueEntry.queue_id, func.count(OnlineQueueEntry.id))
            .filter(OnlineQueueEntry.queue_id.in_(queue_ids))
            .group_by(OnlineQueueEntry.queue_id)
            .all()
        )

        doctor_ids = {
            queue.specialist_id
            for queue in queues
            if getattr(queue, "queue_resource_id", None) is None
            and queue.specialist_id is not None
        }
        doctor_names: dict[int, str | None] = {}
        if doctor_ids:
            doctor_rows = (
                db.query(Doctor.id, User.id, User.full_name)
                .outerjoin(User, Doctor.user_id == User.id)
                .filter(Doctor.id.in_(doctor_ids))
                .all()
            )
            doctor_names = {
                doctor_id: full_name if user_id is not None else f"ID:{doctor_id}"
                for doctor_id, user_id, full_name in doctor_rows
            }

        resource_ids = {
            queue.queue_resource_id
            for queue in queues
            if getattr(queue, "queue_resource_id", None) is not None
        }
        resource_names: dict[int, str] = {}
        if resource_ids:
            resource_names = dict(
                db.query(QueueResource.id, QueueResource.display_name)
                .filter(QueueResource.id.in_(resource_ids))
                .all()
            )

        return entry_counts, doctor_names, resource_names

    def rollback(self) -> None:
        self.repository.rollback()
