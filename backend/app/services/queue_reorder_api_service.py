"""Service layer for queue_reorder endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.crud.queue_resource_routing import resource_start_number
from app.repositories.queue_reorder_api_repository import QueueReorderApiRepository
from app.services.queue_domain_service import QueueDomainReadError, QueueDomainService


@dataclass
class QueueReorderApiDomainError(Exception):
    status_code: int
    detail: str


class QueueReorderApiService:
    """Handles queue reorder business logic and persistence."""

    def __init__(
        self,
        db: Session,
        repository: QueueReorderApiRepository | None = None,
        domain_service: QueueDomainService | None = None,
    ):
        self.db = db
        self.repository = repository or QueueReorderApiRepository(db)
        self.domain_service = domain_service or QueueDomainService(db)

    def _ensure_doctor_can_mutate_queue(self, *, current_user, queue) -> None:
        if current_user.role != "Doctor":
            return

        doctor = self.repository.get_active_doctor_by_user_id(current_user.id)
        if not doctor or queue.specialist_id != doctor.id:
            raise QueueReorderApiDomainError(403, "Нет прав для изменения этой очереди")

    def _registry_floor(self, queue) -> int:
        """Стартовый номер реестра для нумерации очереди (1 = без floor).

        getattr/isinstance: юнит-стабы могут передавать SimpleNamespace-
        очереди и не-Session db (конвенция round-8/10) — для них
        легаси-нумерация позиций без смещения.
        """
        if getattr(queue, "queue_resource_id", None) is None:
            return 1
        if not isinstance(self.db, Session):
            return 1
        return resource_start_number(self.db, queue) or 1

    @staticmethod
    def _queue_info(queue, entries: list) -> dict:
        # QD-2C (Codex round-15 P2): resource-ось — владелец из реестра
        # (display_name + queue_resource_id), не «Неизвестно»/null при
        # живом реестровом владельце; врач-очереди байт-идентичны.
        # getattr: юнит-стабы (SimpleNamespace) — round-8/10 конвенция.
        resource_id = getattr(queue, "queue_resource_id", None)
        if resource_id is not None:
            resource = getattr(queue, "queue_resource", None)
            specialist_name = (
                resource.display_name if resource is not None else "Ресурс очереди"
            )
        elif queue.specialist and queue.specialist.user:
            specialist_name = queue.specialist.user.full_name
        else:
            specialist_name = "Неизвестно"
        return {
            "queue_id": queue.id,
            "day": queue.day.isoformat(),
            "specialist_name": specialist_name,
            "specialist_id": queue.specialist_id,
            "queue_resource_id": resource_id,
            "is_active": queue.active,
            "opened_at": queue.opened_at.isoformat() if queue.opened_at else None,
            "total_entries": len(entries),
            "entries": [
                {
                    "id": entry.id,
                    "number": entry.number,
                    "patient_name": entry.patient_name,
                    "phone": entry.phone,
                    "status": entry.status,
                    "source": entry.source,
                    "created_at": entry.created_at.isoformat(),
                    "called_at": (
                        entry.called_at.isoformat() if entry.called_at else None
                    ),
                }
                for entry in entries
            ],
        }

    def reorder_queue(
        self,
        *,
        queue_id: int,
        entry_orders: list[dict[str, int]],
        current_user,
    ) -> tuple[int, dict]:
        queue = self.repository.get_queue(queue_id)
        if not queue:
            raise QueueReorderApiDomainError(404, "Очередь не найдена")

        self._ensure_doctor_can_mutate_queue(current_user=current_user, queue=queue)

        entries = self.repository.list_active_entries(queue_id=queue_id)
        if not entries:
            raise QueueReorderApiDomainError(404, "В очереди нет активных записей")

        entry_map = {entry.id: entry for entry in entries}
        request_entry_ids = {item["entry_id"] for item in entry_orders}
        existing_entry_ids = set(entry_map.keys())
        if not request_entry_ids.issubset(existing_entry_ids):
            missing_ids = request_entry_ids - existing_entry_ids
            raise QueueReorderApiDomainError(
                400,
                f"Записи с ID {missing_ids} не найдены в очереди",
            )

        max_position = len(entries)
        for item in entry_orders:
            if item["new_position"] > max_position:
                raise QueueReorderApiDomainError(
                    400,
                    (
                        f"Позиция {item['new_position']} превышает размер очереди "
                        f"({max_position})"
                    ),
                )

        # QD-2C (Codex round-15 P2): ресурсная очередь нумеруется от
        # стартового номера реестра (start_number_online, сиды 0059):
        # позиции запроса (1..N) — это ПОЗИЦИИ, а записи хранят НОМЕРА
        # (floor..floor+N-1). Без смещения реордер 40/41 давал бы 1/2,
        # и следующая аллокация переиспользовала бы напечатанный №40.
        # Врач-очереди (floor отсутствует) — байт-идентично.
        base = self._registry_floor(queue)

        updated_count = 0
        for item in entry_orders:
            entry = entry_map[item["entry_id"]]
            new_number = item["new_position"] + (base - 1)
            if entry.number != new_number:
                entry.number = new_number
                updated_count += 1

        self.repository.commit()
        updated_entries = self.repository.list_active_entries(queue_id=queue_id)
        queue_info = self._queue_info(queue, updated_entries)
        return updated_count, queue_info

    def move_queue_entry(
        self,
        *,
        entry_id: int,
        new_position: int,
        current_user,
    ) -> tuple[str, int, dict]:
        entry = self.repository.get_active_entry(entry_id)
        if not entry:
            raise QueueReorderApiDomainError(404, "Запись в очереди не найдена")

        queue = self.repository.get_queue(entry.queue_id)
        if not queue:
            raise QueueReorderApiDomainError(404, "Очередь не найдена")

        self._ensure_doctor_can_mutate_queue(current_user=current_user, queue=queue)

        all_entries = self.repository.list_active_entries(queue_id=entry.queue_id)
        if new_position > len(all_entries):
            raise QueueReorderApiDomainError(
                400,
                f"Позиция {new_position} превышает размер очереди ({len(all_entries)})",
            )

        # QD-2C (Codex round-15 P2): запрос оперирует ПОЗИЦИЯМИ (1..N),
        # записи ресурсной очереди хранят НОМЕРА от floor реестра —
        # переводим позицию в номер-пространство, чтобы сдвиги ±1
        # считались в одной шкале (иначе смешение 40/41 с 1/2).
        base = self._registry_floor(queue)
        new_number = new_position + (base - 1)

        old_number = entry.number
        if old_number == new_number:
            return (
                "Позиция не изменилась",
                0,
                self._queue_info(queue, all_entries),
            )

        updated_count = 0
        if old_number < new_number:
            for other_entry in all_entries:
                if other_entry.id == entry.id:
                    continue
                if old_number < other_entry.number <= new_number:
                    other_entry.number -= 1
                    updated_count += 1
        else:
            for other_entry in all_entries:
                if other_entry.id == entry.id:
                    continue
                if new_number <= other_entry.number < old_number:
                    other_entry.number += 1
                    updated_count += 1

        entry.number = new_number
        updated_count += 1
        self.repository.commit()

        updated_entries = self.repository.list_active_entries(queue_id=entry.queue_id)
        queue_info = self._queue_info(queue, updated_entries)
        return (
            f"Запись перемещена с позиции {old_number} на позицию {new_number}",
            updated_count,
            queue_info,
        )

    def get_queue_status_by_specialist(self, *, specialist_id: int, day: date) -> dict:
        try:
            snapshot = self.domain_service.get_queue_snapshot_by_specialist_day(
                specialist_id=specialist_id,
                day=day,
            )
        except QueueDomainReadError as exc:
            raise QueueReorderApiDomainError(exc.status_code, exc.detail) from exc
        return self._queue_info(snapshot.queue, snapshot.entries)

    def get_queue_status(self, *, queue_id: int) -> dict:
        try:
            snapshot = self.domain_service.get_queue_snapshot(queue_id=queue_id)
        except QueueDomainReadError as exc:
            raise QueueReorderApiDomainError(exc.status_code, exc.detail) from exc
        return self._queue_info(snapshot.queue, snapshot.entries)

    def rollback(self) -> None:
        self.repository.rollback()
