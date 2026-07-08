"""Service layer for display_websocket endpoints."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

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

    @staticmethod
    def _role_name(current_user: object) -> str:
        role = getattr(current_user, "role", "")
        return str(getattr(role, "value", role) or "").strip().lower()

    @staticmethod
    def _same_specialty(left: str | None, right: str | None) -> bool:
        return str(left or "").strip().lower() == str(right or "").strip().lower()

    def _current_doctor_or_403(self, current_user: object) -> object:
        doctor = self.repository.get_active_doctor_by_user_id(
            getattr(current_user, "id", None)
        )
        if not doctor:
            raise DisplayWebSocketApiDomainError(
                status_code=403,
                detail="Doctor profile is required to call queue patients",
            )
        return doctor

    def _ensure_doctor_can_call_queue(
        self,
        *,
        current_user: object,
        queue: object,
    ) -> None:
        if self._role_name(current_user) != "doctor":
            return

        doctor = self._current_doctor_or_403(current_user)
        if getattr(queue, "specialist_id", None) != getattr(doctor, "id", None):
            raise DisplayWebSocketApiDomainError(
                status_code=403,
                detail="Doctor can only call patients from their own queue",
            )

    async def call_patient(
        self,
        *,
        entry_id: int,
        board_ids: list[str],
        current_user: object,
    ) -> dict:
        queue_entry = self.repository.get_queue_entry(entry_id)
        if not queue_entry:
            raise DisplayWebSocketApiDomainError(
                status_code=404,
                detail="Запись в очереди не найдена",
            )

        self._ensure_doctor_can_call_queue(
            current_user=current_user,
            queue=queue_entry.queue,
        )

        queue_entry.status = "called"
        queue_entry.called_at = datetime.now(UTC)
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
            "timestamp": datetime.now(UTC).isoformat(),
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
        current_user: object,
    ) -> dict:
        if self._role_name(current_user) == "doctor":
            doctor = self._current_doctor_or_403(current_user)
            if not self._same_specialty(getattr(doctor, "specialty", None), specialty):
                raise DisplayWebSocketApiDomainError(
                    status_code=403,
                    detail="Doctor can only quick-call patients for their own specialty",
                )
        else:
            doctor = self.repository.get_active_doctor_by_specialty(specialty)
        if not doctor:
            raise DisplayWebSocketApiDomainError(
                status_code=404,
                detail=f"Врач специальности {specialty} не найден",
            )

        daily_queue = self.repository.get_daily_queue_for_specialist(
            day=date.today(),
            specialist_id=doctor.id,
        )

        if daily_queue:
            self._ensure_doctor_can_call_queue(
                current_user=current_user,
                queue=daily_queue,
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
            current_user=current_user,
        )
