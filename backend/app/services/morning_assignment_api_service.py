"""Service layer for morning_assignment endpoints."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.repositories.morning_assignment_api_repository import (
    MorningAssignmentApiRepository,
)
from app.services.morning_assignment import (
    MorningAssignmentService,
    get_assignment_stats,
    run_morning_assignment,
)


class MorningAssignmentApiService:
    """Builds payloads for morning assignment API endpoints."""

    def __init__(
        self,
        db: Session,
        repository: MorningAssignmentApiRepository | None = None,
    ):
        self.repository = repository or MorningAssignmentApiRepository(db)

    @staticmethod
    def parse_target_date(target_date: str | None) -> date:
        if not target_date:
            return date.today()
        return datetime.strptime(target_date, "%Y-%m-%d").date()

    def run_assignment_for_date(self, *, target_date: date) -> dict:
        return run_morning_assignment(target_date)

    def get_stats_for_date(self, *, target_date: date) -> dict:
        return get_assignment_stats(target_date)

    def manual_assignment_for_visits(self, *, visit_ids: list[int], force: bool) -> dict:
        with MorningAssignmentService() as service:
            service.db = self.repository.db
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
                        visit.status = "open"
                        results.append(
                            {
                                "visit_id": visit_id,
                                "success": True,
                                "message": f"Присвоено {len(queue_assignments)} номеров",
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
                except Exception as exc:  # noqa: BLE001
                    results.append(
                        {
                            "visit_id": visit_id,
                            "success": False,
                            "message": f"Ошибка: {str(exc)}",
                        }
                    )

            self.repository.commit()
            return {
                "success": True,
                "message": f"Обработано {len(visit_ids)} визитов",
                "results": results,
            }

    def get_pending_visits_payload(self, *, target_date: date) -> dict:
        with MorningAssignmentService() as service:
            service.db = self.repository.db
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
        queue_summary = []

        for queue in queues:
            entries_count = self.repository.count_queue_entries(queue_id=queue.id)
            doctor = self.repository.get_doctor(queue.specialist_id)
            doctor_name = (
                doctor.user.full_name
                if doctor and doctor.user
                else f"ID:{queue.specialist_id}"
            )
            queue_summary.append(
                {
                    "queue_id": queue.id,
                    "queue_tag": queue.queue_tag or "general",
                    "doctor_name": doctor_name,
                    "doctor_id": queue.specialist_id,
                    "entries_count": entries_count,
                    "active": queue.active,
                    "opened_at": queue.opened_at.isoformat() if queue.opened_at else None,
                }
            )

        return {
            "success": True,
            "date": target_date.isoformat(),
            "queues_count": len(queues),
            "total_entries": sum(item["entries_count"] for item in queue_summary),
            "queues": queue_summary,
        }

    def rollback(self) -> None:
        self.repository.rollback()
