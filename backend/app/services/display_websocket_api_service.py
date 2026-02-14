"""Service layer for display_websocket endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.repositories.display_websocket_api_repository import (
    DisplayWebSocketApiRepository,
)
from app.services.display_websocket import get_display_manager


@dataclass
class DisplayWebSocketApiDomainError(Exception):
    status_code: int
    detail: str


class DisplayWebSocketApiService:
    """Builds payloads and performs queue actions for display websocket API."""

    def __init__(
        self,
        db: Session,
        repository: DisplayWebSocketApiRepository | None = None,
        manager_provider: Callable = get_display_manager,  # type: ignore[type-arg]
    ):
        self.repository = repository or DisplayWebSocketApiRepository(db)
        self._manager_provider = manager_provider

    async def call_patient(
        self,
        *,
        entry_id: int,
        board_ids: list[str],
    ) -> dict:
        queue_entry = self.repository.get_queue_entry(entry_id)
        if not queue_entry:
            raise DisplayWebSocketApiDomainError(
                status_code=404,
                detail="Запись в очереди не найдена",
            )

        queue_entry.status = "called"
        queue_entry.called_at = datetime.utcnow()
        self.repository.save()

        doctor = queue_entry.queue.specialist
        doctor_name = doctor.user.full_name if doctor and doctor.user else "Врач"
        cabinet = doctor.cabinet if doctor else None

        manager = self._manager_provider()
        await manager.broadcast_patient_call(
            queue_entry=queue_entry,
            doctor_name=doctor_name,
            cabinet=cabinet,
            board_ids=board_ids if board_ids else None,
        )

        return {
            "success": True,
            "message": f"Пациент #{queue_entry.number} вызван на табло",
            "call_data": {
                "number": queue_entry.number,
                "patient_name": queue_entry.patient_name,
                "doctor": doctor_name,
                "cabinet": cabinet,
                "called_at": queue_entry.called_at.isoformat(),
            },
            "boards_notified": len(board_ids) if board_ids else len(manager.connections),
        }

    def get_department_queue_state_payload(self, *, department: str) -> dict:
        today = date.today()
        queue_entries = self.repository.list_active_entries_for_day(day=today)

        filtered_entries = []
        for entry in queue_entries:
            filtered_entries.append(
                {
                    "id": entry.id,
                    "number": entry.number,
                    "patient_name": entry.patient_name,
                    "status": entry.status,
                    "source": entry.source,
                    "created_at": (
                        entry.created_at.isoformat() if entry.created_at else None
                    ),
                }
            )

        return {
            "type": "queue_state",
            "department": department,
            "timestamp": datetime.utcnow().isoformat(),
            "entries": filtered_entries,
            "total_waiting": len(
                [entry for entry in filtered_entries if entry["status"] == "waiting"]
            ),
            "current_number": max(
                [entry["number"] for entry in filtered_entries],
                default=0,
            ),
        }

    async def quick_call_next(
        self,
        *,
        specialty: str,
        board_id: str | None,
    ) -> dict:
        doctor = self.repository.get_active_doctor_by_specialty(specialty)
        if not doctor:
            raise DisplayWebSocketApiDomainError(
                status_code=404,
                detail=f"Врач специальности {specialty} не найден",
            )

        doctor_user_id = doctor.user_id if doctor.user_id else None
        daily_queue = None
        if doctor_user_id:
            daily_queue = self.repository.get_daily_queue_for_specialist(
                day=date.today(),
                specialist_id=doctor_user_id,
            )

        if not daily_queue:
            raise DisplayWebSocketApiDomainError(
                status_code=404,
                detail="Очередь на сегодня не найдена",
            )

        next_entry = self.repository.get_next_waiting_entry(queue_id=daily_queue.id)
        if not next_entry:
            return {
                "success": False,
                "message": "Нет пациентов в очереди",
                "queue_empty": True,
            }

        return await self.call_patient(
            entry_id=next_entry.id,
            board_ids=[board_id] if board_id else [],
        )
