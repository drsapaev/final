"""Service layer for queue cabinet management endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.queue_cabinet_management_api_repository import (
    QueueCabinetManagementApiRepository,
)


@dataclass
class QueueCabinetManagementDomainError(Exception):
    status_code: int
    detail: str


class QueueCabinetManagementApiService:
    """Handles payload generation and updates for queue cabinet management."""

    def __init__(
        self,
        db: Session,
        repository: QueueCabinetManagementApiRepository | None = None,
    ):
        self.repository = repository or QueueCabinetManagementApiRepository(db)

    @staticmethod
    def _parse_date(value: str, *, error_detail: str) -> date:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise QueueCabinetManagementDomainError(400, error_detail) from exc

    def _resolve_specialist_name(self, specialist_id: int) -> str:
        specialist = self.repository.get_doctor(specialist_id)
        if specialist and specialist.user:
            return specialist.user.full_name
        return f"Специалист #{specialist_id}"

    def get_queues_cabinet_info(
        self,
        *,
        day: str | None,
        specialist_id: int | None,
        cabinet_number: str | None,
    ) -> list[dict[str, Any]]:
        day_obj = None
        if day:
            day_obj = self._parse_date(
                day,
                error_detail="Неверный формат даты. Используйте YYYY-MM-DD",
            )

        queues = self.repository.list_daily_queues(
            day_obj=day_obj,
            specialist_id=specialist_id,
            cabinet_number=cabinet_number,
        )

        return [
            {
                "id": queue.id,
                "day": queue.day.isoformat(),
                "specialist_id": queue.specialist_id,
                "specialist_name": self._resolve_specialist_name(queue.specialist_id),
                "queue_tag": queue.queue_tag,
                "cabinet_number": queue.cabinet_number,
                "cabinet_floor": queue.cabinet_floor,
                "cabinet_building": queue.cabinet_building,
                "entries_count": self.repository.count_entries(queue_id=queue.id),
                "active": queue.active,
            }
            for queue in queues
        ]

    def get_queue_cabinet_info(self, *, queue_id: int) -> dict[str, Any]:
        queue = self.repository.get_daily_queue(queue_id)
        if not queue:
            raise QueueCabinetManagementDomainError(404, "Очередь не найдена")

        return {
            "id": queue.id,
            "day": queue.day.isoformat(),
            "specialist_id": queue.specialist_id,
            "specialist_name": self._resolve_specialist_name(queue.specialist_id),
            "queue_tag": queue.queue_tag,
            "cabinet_number": queue.cabinet_number,
            "cabinet_floor": queue.cabinet_floor,
            "cabinet_building": queue.cabinet_building,
            "entries_count": self.repository.count_entries(queue_id=queue.id),
            "active": queue.active,
        }

    def update_queue_cabinet_info(
        self,
        *,
        queue_id: int,
        cabinet_info: dict[str, Any],
        updated_by: str,
    ) -> dict[str, Any]:
        queue = self.repository.get_daily_queue(queue_id)
        if not queue:
            raise QueueCabinetManagementDomainError(404, "Очередь не найдена")

        updated = False
        if cabinet_info.get("cabinet_number") is not None:
            queue.cabinet_number = cabinet_info["cabinet_number"]
            updated = True
        if cabinet_info.get("cabinet_floor") is not None:
            queue.cabinet_floor = cabinet_info["cabinet_floor"]
            updated = True
        if cabinet_info.get("cabinet_building") is not None:
            queue.cabinet_building = cabinet_info["cabinet_building"]
            updated = True

        if updated:
            self.repository.commit()
            self.repository.refresh(queue)

        return {
            "success": True,
            "message": "Информация о кабинете обновлена",
            "queue_id": queue_id,
            "cabinet_info": {
                "cabinet_number": queue.cabinet_number,
                "cabinet_floor": queue.cabinet_floor,
                "cabinet_building": queue.cabinet_building,
            },
            "updated_by": updated_by,
            "updated_at": datetime.utcnow().isoformat(),
        }

    def bulk_update_cabinet_info(
        self,
        *,
        updates: list[dict[str, Any]],
        updated_by: str,
    ) -> dict[str, Any]:
        updated_queues = []
        errors = []

        for update in updates:
            queue = self.repository.get_daily_queue(update["queue_id"])
            if not queue:
                errors.append({"queue_id": update["queue_id"], "error": "Очередь не найдена"})
                continue

            cabinet_info = update["cabinet_info"]
            updated = False

            if cabinet_info.get("cabinet_number") is not None:
                queue.cabinet_number = cabinet_info["cabinet_number"]
                updated = True
            if cabinet_info.get("cabinet_floor") is not None:
                queue.cabinet_floor = cabinet_info["cabinet_floor"]
                updated = True
            if cabinet_info.get("cabinet_building") is not None:
                queue.cabinet_building = cabinet_info["cabinet_building"]
                updated = True

            if updated:
                updated_queues.append(
                    {
                        "queue_id": update["queue_id"],
                        "cabinet_info": {
                            "cabinet_number": queue.cabinet_number,
                            "cabinet_floor": queue.cabinet_floor,
                            "cabinet_building": queue.cabinet_building,
                        },
                    }
                )

        if updated_queues:
            self.repository.commit()

        return {
            "success": True,
            "message": f"Обновлено {len(updated_queues)} очередей",
            "updated_queues": updated_queues,
            "errors": errors,
            "updated_by": updated_by,
            "updated_at": datetime.utcnow().isoformat(),
        }

    def sync_cabinet_info_from_doctors(
        self,
        *,
        day: str | None,
        specialist_id: int | None,
        synced_by: str,
    ) -> dict[str, Any]:
        if day:
            day_obj = self._parse_date(
                day,
                error_detail="Неверный формат даты. Используйте YYYY-MM-DD",
            )
        else:
            day_obj = date.today()

        queues = self.repository.list_queues_for_day(
            day_obj=day_obj,
            specialist_id=specialist_id,
        )

        updated_count = 0
        errors = []

        for queue in queues:
            try:
                doctor = self.repository.get_doctor(queue.specialist_id)
                if doctor and doctor.cabinet and queue.cabinet_number != doctor.cabinet:
                    queue.cabinet_number = doctor.cabinet
                    updated_count += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    {
                        "queue_id": queue.id,
                        "specialist_id": queue.specialist_id,
                        "error": str(exc),
                    }
                )

        if updated_count > 0:
            self.repository.commit()

        return {
            "success": True,
            "message": f"Синхронизировано {updated_count} очередей",
            "updated_count": updated_count,
            "total_queues": len(queues),
            "errors": errors,
            "sync_date": day_obj.isoformat(),
            "synced_by": synced_by,
            "synced_at": datetime.utcnow().isoformat(),
        }

    def get_cabinet_statistics(
        self,
        *,
        date_from: str | None,
        date_to: str | None,
    ) -> dict[str, Any]:
        date_from_obj = None
        date_to_obj = None
        if date_from:
            date_from_obj = self._parse_date(
                date_from,
                error_detail="Неверный формат даты начала. Используйте YYYY-MM-DD",
            )
        if date_to:
            date_to_obj = self._parse_date(
                date_to,
                error_detail="Неверный формат даты окончания. Используйте YYYY-MM-DD",
            )

        queues = self.repository.list_queues_for_period(
            date_from=date_from_obj,
            date_to=date_to_obj,
        )

        cabinet_stats: dict[str, dict[str, Any]] = {}
        total_queues = len(queues)
        queues_with_cabinet = 0

        for queue in queues:
            if not queue.cabinet_number:
                continue

            queues_with_cabinet += 1
            if queue.cabinet_number not in cabinet_stats:
                cabinet_stats[queue.cabinet_number] = {
                    "cabinet_number": queue.cabinet_number,
                    "cabinet_floor": queue.cabinet_floor,
                    "cabinet_building": queue.cabinet_building,
                    "queue_count": 0,
                    "total_entries": 0,
                    "specialists": set(),
                }

            cabinet_stats[queue.cabinet_number]["queue_count"] += 1
            cabinet_stats[queue.cabinet_number]["specialists"].add(queue.specialist_id)
            cabinet_stats[queue.cabinet_number]["total_entries"] += self.repository.count_entries(
                queue_id=queue.id
            )

        cabinet_list = []
        for stats in cabinet_stats.values():
            stats["specialists_count"] = len(stats["specialists"])
            del stats["specialists"]
            cabinet_list.append(stats)
        cabinet_list.sort(key=lambda item: item["queue_count"], reverse=True)

        return {
            "success": True,
            "statistics": {
                "total_queues": total_queues,
                "queues_with_cabinet": queues_with_cabinet,
                "queues_without_cabinet": total_queues - queues_with_cabinet,
                "cabinet_coverage": round(
                    (queues_with_cabinet / total_queues * 100) if total_queues else 0,
                    2,
                ),
                "unique_cabinets": len(cabinet_stats),
                "cabinets": cabinet_list,
            },
            "period": {"date_from": date_from, "date_to": date_to},
        }

    def rollback(self) -> None:
        self.repository.rollback()
