"""Queue domain boundary introduced in Wave 2C Phase 1."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.crud import queue_resource_routing
from app.crud.clinic import get_queue_settings
from app.repositories.queue_read_repository import QueueReadRepository
from app.services.queue_service import queue_service
from app.services.queue_status import REORDER_ACTIVE_RAW_STATUSES


@dataclass
class QueueDomainReadError(Exception):
    status_code: int
    detail: str


@dataclass(frozen=True)
class QueueSnapshot:
    queue: object
    entries: list[object]


class QueueDomainService:
    """Owns queue-domain boundaries without migrating mutations yet."""

    def __init__(
        self,
        db: Session,
        read_repository: QueueReadRepository | None = None,
        get_settings: Callable[[Session], dict] | None = None,
        allocator_service: Any | None = None,
    ):
        self.db = db
        self.read_repository = read_repository or QueueReadRepository(db)
        self._get_settings = get_settings or get_queue_settings
        self.allocator_service = allocator_service or queue_service

    def get_queue_snapshot(self, *, queue_id: int) -> QueueSnapshot:
        queue = self.read_repository.get_queue(queue_id)
        if not queue:
            raise QueueDomainReadError(404, "Очередь не найдена")

        entries = self.read_repository.list_snapshot_entries(
            queue_id=queue_id,
            statuses=REORDER_ACTIVE_RAW_STATUSES,
        )
        return QueueSnapshot(queue=queue, entries=entries)

    def get_queue_snapshot_by_specialist_day(
        self,
        *,
        specialist_id: int,
        day: date,
    ) -> QueueSnapshot:
        queue = self.read_repository.get_queue_by_specialist_day(
            specialist_id=specialist_id,
            day=day,
        )
        if not queue:
            raise QueueDomainReadError(404, "Очередь не найдена")

        entries = self.read_repository.list_snapshot_entries(
            queue_id=queue.id,
            statuses=REORDER_ACTIVE_RAW_STATUSES,
        )
        return QueueSnapshot(queue=queue, entries=entries)

    def _resolve_specialist_name(self, specialist_id: int) -> str:
        specialist = self.read_repository.get_doctor(specialist_id)
        if specialist and specialist.user:
            user = specialist.user
            return user.full_name or user.username or f"Специалист #{specialist_id}"
        return f"Специалист #{specialist_id}"

    def _build_cabinet_payload(self, queue: object) -> dict[str, Any]:
        # QD-2C (Codex round-8 P1 / round-10 P2): resource-axis очередь
        # (queue_resource_id — включая BRIDGED строки 0059, у которых
        # specialist_id тоже установлен; контракт DailyQueueOut/GQL
        # классифицирует мост как resource) — врач-ось отсутствует по
        # дизайну: владелец = реестр, кабинет — из строки очереди
        # (default_cabinet копируется при создании), sync-семантика
        # «нет связанного врача» не является integrity-проблемой.
        if getattr(queue, "queue_resource_id", None) is not None:
            resource = getattr(queue, "queue_resource", None)
            queue_cabinet = queue.cabinet_number
            return {
                "id": queue.id,
                "day": queue.day.isoformat(),
                # the bridge KEEPS the doctor axis (0059 backfill shape);
                # pure resource rows carry None
                "specialist_id": queue.specialist_id,
                "specialist_name": (
                    resource.display_name if resource else "Ресурс очереди"
                ),
                "queue_tag": queue.queue_tag,
                "cabinet_number": queue_cabinet,
                "doctor_cabinet": None,
                "effective_cabinet": queue_cabinet,
                "cabinet_floor": queue.cabinet_floor,
                "cabinet_building": queue.cabinet_building,
                "entries_count": self.read_repository.count_entries(queue_id=queue.id),
                "active": queue.active,
                "linked_doctor_found": False,
                "doctor_has_cabinet": False,
                "sync_status": "resource_owned",
                "integrity_warnings": (
                    [] if queue_cabinet else ["effective_cabinet_missing"]
                ),
            }
        doctor = self.read_repository.get_doctor(queue.specialist_id)
        doctor_cabinet = getattr(doctor, "cabinet", None) if doctor else None
        linked_doctor_found = doctor is not None
        doctor_has_cabinet = bool(doctor_cabinet)
        queue_cabinet = queue.cabinet_number
        effective_cabinet = queue_cabinet or doctor_cabinet
        integrity_warnings: list[str] = []

        if not linked_doctor_found:
            sync_status = "missing_doctor"
            integrity_warnings.append("linked_doctor_missing")
        elif not doctor_has_cabinet:
            sync_status = "doctor_cabinet_missing"
            integrity_warnings.append("doctor_cabinet_missing")
        elif queue_cabinet != doctor_cabinet:
            sync_status = "stale"
            integrity_warnings.append("queue_cabinet_stale")
        else:
            sync_status = "synced"

        if not effective_cabinet:
            integrity_warnings.append("effective_cabinet_missing")

        return {
            "id": queue.id,
            "day": queue.day.isoformat(),
            "specialist_id": queue.specialist_id,
            "specialist_name": self._resolve_specialist_name(queue.specialist_id),
            "queue_tag": queue.queue_tag,
            "cabinet_number": queue_cabinet,
            "doctor_cabinet": doctor_cabinet,
            "effective_cabinet": effective_cabinet,
            "cabinet_floor": queue.cabinet_floor,
            "cabinet_building": queue.cabinet_building,
            "entries_count": self.read_repository.count_entries(queue_id=queue.id),
            "active": queue.active,
            "linked_doctor_found": linked_doctor_found,
            "doctor_has_cabinet": doctor_has_cabinet,
            "sync_status": sync_status,
            "integrity_warnings": integrity_warnings,
        }

    def list_queue_cabinet_info(
        self,
        *,
        day: date | None,
        specialist_id: int | None,
        cabinet_number: str | None,
    ) -> list[dict[str, Any]]:
        queues = self.read_repository.list_daily_queues(
            day_obj=day,
            specialist_id=specialist_id,
            cabinet_number=cabinet_number,
        )
        return [self._build_cabinet_payload(queue) for queue in queues]

    def get_queue_cabinet_info(self, *, queue_id: int) -> dict[str, Any]:
        queue = self.read_repository.get_queue(queue_id)
        if not queue:
            raise QueueDomainReadError(404, "Очередь не найдена")
        return self._build_cabinet_payload(queue)

    def get_queue_limits_status(
        self,
        *,
        day: date,
        specialty: str | None,
    ) -> list[dict[str, Any]]:
        queue_settings = self._get_settings(self.db) or {}
        max_per_day_settings = queue_settings.get("max_per_day", {})
        doctors = self.read_repository.list_active_doctors(specialty=specialty)

        result: list[dict[str, Any]] = []
        for doctor in doctors:
            # Preserve current runtime behavior: limits read paths resolve DailyQueue
            # by Doctor.user_id even though DailyQueue.specialist_id is modeled
            # against doctors.id.
            # QD-2C (Codex round-10 P2): registry-tag врач — usage/кап/
            # открытость читаются с (day, tag)-ПОВЕРХНОСТИ (могла быть
            # создана ресурсной после переключения), иначе отчёт
            # показывает нулевую загрузку сразу после смены лимита.
            # isinstance: unit-стабы могут передавать не-Session db —
            # для них легаси-путь (их врачи не registry-теги).
            surface = None
            if doctor.specialty and isinstance(self.db, Session):
                surface = (
                    queue_resource_routing.resolve_registry_tag_queue_for_specialist(
                        self.db, day, doctor.id, None
                    )
                )
            if surface is not None:
                daily_queue = surface
                current_entries = self.read_repository.count_entries(
                    queue_id=daily_queue.id
                )
                queue_opened = daily_queue.opened_at is not None
                max_entries = daily_queue.max_online_entries or max_per_day_settings.get(
                    doctor.specialty, 15
                )
            else:
                daily_queue = self.read_repository.get_queue_by_specialist_day(
                    specialist_id=doctor.user_id,
                    day=day,
                )
                current_entries = 0
                queue_opened = False
                if daily_queue:
                    current_entries = self.read_repository.count_entries(
                        queue_id=daily_queue.id
                    )
                    queue_opened = daily_queue.opened_at is not None
                max_entries = max_per_day_settings.get(doctor.specialty, 15)
            result.append(
                {
                    "doctor_id": doctor.id,
                    "doctor_name": (
                        doctor.user.full_name if doctor.user else f"Doctor #{doctor.id}"
                    ),
                    "specialty": doctor.specialty,
                    "cabinet": doctor.cabinet,
                    "day": day,
                    "current_entries": current_entries,
                    "max_entries": max_entries,
                    "limit_reached": current_entries >= max_entries,
                    "queue_opened": queue_opened,
                    "online_available": (not queue_opened and current_entries < max_entries),
                }
            )

        return result
    def get_queue_groups_payload(self) -> dict[str, Any]:
        from app.services.service_mapping import (
            QUEUE_GROUPS,
            get_queue_group_for_service,
        )

        groups: dict[str, dict[str, Any]] = {}
        for key, data in QUEUE_GROUPS.items():
            groups[key] = {
                "display_name": data["display_name"],
                "display_name_uz": data.get("display_name_uz"),
                "service_codes": data.get("service_codes", []),
                "service_prefixes": data.get("service_prefixes", []),
                "exclude_codes": data.get("exclude_codes", []),
                "queue_tag": data["queue_tag"],
                "tab_key": data["tab_key"],
            }

        code_to_group: dict[str, str] = {}
        for key, data in QUEUE_GROUPS.items():
            for code in data.get("service_codes", []):
                code_to_group[code] = key

        try:
            services = self.read_repository.list_active_services()
            for service in services:
                if service.service_code:
                    group = get_queue_group_for_service(service.service_code)
                    if group:
                        code_to_group[service.service_code] = group
        except Exception:
            pass

        tab_to_group = {data["tab_key"]: key for key, data in QUEUE_GROUPS.items()}
        return {
            "groups": groups,
            "code_to_group": code_to_group,
            "tab_to_group": tab_to_group,
        }

    def get_service_code_mappings_payload(self) -> dict[str, Any]:
        from app.services.service_mapping import SPECIALTY_ALIASES

        specialty_to_code = {
            "cardiology": "K01",
            "cardio": "K01",
            "dermatology": "D01",
            "derma": "D01",
            "stomatology": "S01",
            "dental": "S01",
            "laboratory": "L01",
            "lab": "L01",
            "echokg": "K10",
            "procedures": "P01",
            "cosmetology": "C01",
        }

        code_to_name = {
            "K01": "Консультация кардиолога",
            "K10": "ЭхоКГ",
            "D01": "Консультация дерматолога",
            "S01": "Консультация стоматолога",
            "L01": "Лабораторные анализы",
            "P01": "Процедуры",
            "C01": "Косметология",
        }

        category_mapping = {
            "cardiology": "K",
            "dermatology": "D",
            "laboratory": "L",
            "stomatology": "S",
            "cosmetology": "C",
            "procedures": "P",
        }

        try:
            services = self.read_repository.list_active_services()
            for service in services:
                if service.service_code and service.name:
                    code_to_name[service.service_code] = service.name
                if service.queue_tag and service.service_code:
                    specialty_to_code[service.queue_tag] = service.service_code
        except Exception:
            pass

        return {
            "specialty_to_code": specialty_to_code,
            "code_to_name": code_to_name,
            "category_mapping": category_mapping,
            "specialty_aliases": SPECIALTY_ALIASES,
        }

    def allocate_ticket(
        self,
        *,
        allocation_mode: Literal["create_entry", "join_with_token"] = "create_entry",
        **kwargs: Any,
    ) -> Any:
        """Compatibility boundary for current allocator behavior.

        Phase 2 keeps runtime semantics unchanged. This method is only a public
        queue-domain facade over the existing allocators:
        - ``create_entry`` delegates to ``queue_service.create_queue_entry()``.
        - ``join_with_token`` delegates to ``queue_service.join_queue_with_token()``.
        """

        if allocation_mode == "create_entry":
            return self.allocator_service.create_queue_entry(db=self.db, **kwargs)
        if allocation_mode == "join_with_token":
            return self.allocator_service.join_queue_with_token(db=self.db, **kwargs)
        raise ValueError(f"Unsupported queue allocation mode: {allocation_mode}")

    def enqueue(self, **_: Any) -> QueueSnapshot:
        raise NotImplementedError("QueueDomainService.enqueue is a Phase 2 method")

    def call_next(self, **_: Any) -> QueueSnapshot:
        raise NotImplementedError("QueueDomainService.call_next is a Phase 2 method")

    def mark_in_service(self, **_: Any) -> QueueSnapshot:
        raise NotImplementedError(
            "QueueDomainService.mark_in_service is a Phase 2 method"
        )

    def complete_visit(self, **_: Any) -> QueueSnapshot:
        raise NotImplementedError(
            "QueueDomainService.complete_visit is a Phase 2 method"
        )

    def cancel_queue_link(self, **_: Any) -> QueueSnapshot:
        raise NotImplementedError(
            "QueueDomainService.cancel_queue_link is a Phase 2 method"
        )

    def reschedule_queue_link(self, **_: Any) -> QueueSnapshot:
        raise NotImplementedError(
            "QueueDomainService.reschedule_queue_link is a Phase 2 method"
        )
