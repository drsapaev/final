"""Service layer for queue cabinet management endpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.crud.clinic import clinic_today
from app.repositories.queue_cabinet_management_api_repository import (
    QueueCabinetManagementApiRepository,
)
from app.services.queue_status import (
    POSITION_VISIBLE_RAW_STATUSES,
    QUEUE_STATUS_ALIASES,
    normalize_queue_status,
)

logger = logging.getLogger(__name__)

_CABINET_REASSIGNMENT_REASON_CODES = frozenset(
    {
        "room_unavailable",
        "equipment_issue",
        "schedule_change",
        "administrative_correction",
    }
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
        self.db = db
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
            user = specialist.user
            return user.full_name or user.username or f"Специалист #{specialist_id}"
        return f"Специалист #{specialist_id}"

    def _doctor_for_queue(self, queue):
        specialist_id = getattr(queue, "specialist_id", None)
        if specialist_id is None or not hasattr(self.repository, "get_doctor"):
            return None
        return self.repository.get_doctor(specialist_id)

    def _assign_queue_cabinet_number(self, queue, value: Any) -> None:
        doctor = self._doctor_for_queue(queue)
        if doctor and getattr(doctor, "cabinet", None):
            raise QueueCabinetManagementDomainError(
                400,
                "Канонический номер кабинета нельзя менять из этой панели. Обновите кабинет в карточке врача и выполните синхронизацию.",
            )
        queue.cabinet_number = value

    def _build_queue_payload(self, queue) -> dict[str, Any]:
        queue_id = getattr(queue, "id", None)
        queue_day = getattr(queue, "day", None)
        specialist_id = getattr(queue, "specialist_id", None)
        doctor = self._doctor_for_queue(queue)
        doctor_cabinet = getattr(doctor, "cabinet", None) if doctor else None
        linked_doctor_found = doctor is not None
        doctor_has_cabinet = bool(doctor_cabinet)
        queue_cabinet = getattr(queue, "cabinet_number", None)
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
            "id": queue_id,
            "day": queue_day.isoformat() if queue_day else None,
            "specialist_id": specialist_id,
            "specialist_name": (
                self._resolve_specialist_name(specialist_id)
                if specialist_id is not None
                else None
            ),
            "queue_tag": getattr(queue, "queue_tag", None),
            "cabinet_number": queue_cabinet,
            "doctor_cabinet": doctor_cabinet,
            "effective_cabinet": effective_cabinet,
            "cabinet_floor": getattr(queue, "cabinet_floor", None),
            "cabinet_building": getattr(queue, "cabinet_building", None),
            "entries_count": (
                self.repository.count_entries(queue_id=queue_id)
                if queue_id is not None and hasattr(self.repository, "count_entries")
                else 0
            ),
            "active": getattr(queue, "active", None),
            "linked_doctor_found": linked_doctor_found,
            "doctor_has_cabinet": doctor_has_cabinet,
            "sync_status": sync_status,
            "integrity_warnings": integrity_warnings,
        }

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

        return [self._build_queue_payload(queue) for queue in queues]

    def get_queue_cabinet_info(self, *, queue_id: int) -> dict[str, Any]:
        queue = self.repository.get_daily_queue(queue_id)
        if not queue:
            raise QueueCabinetManagementDomainError(404, "Очередь не найдена")

        return self._build_queue_payload(queue)

    @staticmethod
    def _preview_owner(queue) -> dict[str, Any]:
        resource_id = getattr(queue, "queue_resource_id", None)
        if resource_id is not None:
            resource = getattr(queue, "queue_resource", None)
            if resource is None:
                raise QueueCabinetManagementDomainError(
                    409, "Не удалось однозначно определить владельца очереди"
                )
            return {
                "owner_type": "resource",
                "owner_id": resource_id,
                "owner_name": resource.display_name,
                "owner_default_cabinet": resource.default_cabinet,
            }

        specialist_id = getattr(queue, "specialist_id", None)
        specialist = getattr(queue, "specialist", None)
        if specialist_id is None or specialist is None:
            raise QueueCabinetManagementDomainError(
                409, "Не удалось однозначно определить владельца очереди"
            )

        user = getattr(specialist, "user", None)
        owner_name = (
            (getattr(user, "full_name", None) or getattr(user, "username", None))
            if user is not None
            else None
        ) or f"Специалист #{specialist_id}"
        return {
            "owner_type": "doctor",
            "owner_id": specialist_id,
            "owner_name": owner_name,
            "owner_default_cabinet": getattr(specialist, "cabinet", None),
        }

    def _blocking_reasons_by_queue(
        self, *, queue_ids: list[int]
    ) -> dict[int, list[str]]:
        blocking_canonical_statuses = {
            status for status in POSITION_VISIBLE_RAW_STATUSES if status != "waiting"
        }
        blocking_statuses = tuple(
            sorted(
                blocking_canonical_statuses
                | {
                    raw_status
                    for raw_status, canonical_status in QUEUE_STATUS_ALIASES.items()
                    if canonical_status in blocking_canonical_statuses
                }
            )
        )
        entry_statuses = self.repository.list_entry_statuses_by_queue_ids(
            queue_ids=queue_ids,
            statuses=blocking_statuses,
        )
        queues_with_active_execution = (
            self.repository.list_queue_ids_with_active_service_execution(
                queue_ids=queue_ids
            )
        )
        result: dict[int, list[str]] = {}
        for queue_id in queue_ids:
            blocking_reasons: list[str] = []
            statuses = {
                normalize_queue_status(status)
                for status in entry_statuses.get(queue_id, set())
            }
            if "called" in statuses:
                blocking_reasons.append("patient_called")
            if statuses.intersection({"in_service", "diagnostics"}):
                blocking_reasons.append("clinical_work_in_progress")
            if queue_id in queues_with_active_execution:
                blocking_reasons.append("active_service_execution")
            result[queue_id] = blocking_reasons
        return result

    def preview_cabinet_reassignment(
        self, *, queue_ids: list[int], new_cabinet_number: str | None
    ) -> dict[str, Any]:
        """Read-only preview; actual reassignment belongs to the T09.2 command."""
        if (
            not queue_ids
            or any(type(queue_id) is not int or queue_id <= 0 for queue_id in queue_ids)
            or len(set(queue_ids)) != len(queue_ids)
        ):
            raise QueueCabinetManagementDomainError(
                422, "Укажите уникальные положительные ID очередей"
            )

        clinic_day = clinic_today(self.db)
        queues = self.repository.list_daily_queues_by_ids(queue_ids=queue_ids)
        queues_by_id = {queue.id: queue for queue in queues}
        if len(queues_by_id) != len(queue_ids):
            raise QueueCabinetManagementDomainError(
                404, "Одна или несколько очередей не найдены"
            )
        if any(queue.day != clinic_day for queue in queues):
            raise QueueCabinetManagementDomainError(
                409, "Preview доступен только для очередей текущего дня клиники"
            )

        waiting_counts = self.repository.count_waiting_entries_by_queue_ids(
            queue_ids=queue_ids
        )
        blocking_reasons_by_queue = self._blocking_reasons_by_queue(queue_ids=queue_ids)

        items: list[dict[str, Any]] = []
        for queue_id in queue_ids:
            queue = queues_by_id[queue_id]
            blocking_reasons = blocking_reasons_by_queue[queue_id]

            items.append(
                {
                    "queue_id": queue_id,
                    "queue_day": queue.day,
                    **self._preview_owner(queue),
                    "old_cabinet_number": queue.cabinet_number,
                    "new_cabinet_number": new_cabinet_number,
                    "waiting_count": waiting_counts.get(queue_id, 0),
                    "blocking_reasons": blocking_reasons,
                    "can_apply": not blocking_reasons,
                }
            )

        return {
            "clinic_day": clinic_day,
            "items": items,
            "can_apply": all(item["can_apply"] for item in items),
        }

    def apply_cabinet_reassignment(
        self,
        *,
        targets: list[dict[str, Any]],
        new_cabinet_number: str | None,
        reason_code: str,
        actor_user_id: int,
        actor_role: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Apply an explicit same-day cabinet change with one strict audit boundary."""
        queue_ids = [target.get("queue_id") for target in targets]
        if (
            not targets
            or any(type(queue_id) is not int or queue_id <= 0 for queue_id in queue_ids)
            or len(set(queue_ids)) != len(queue_ids)
        ):
            raise QueueCabinetManagementDomainError(
                422, "Укажите уникальные положительные ID очередей"
            )
        if reason_code not in _CABINET_REASSIGNMENT_REASON_CODES:
            raise QueueCabinetManagementDomainError(
                422, "Укажите допустимую кодовую причину изменения кабинета"
            )
        if new_cabinet_number is not None:
            new_cabinet_number = new_cabinet_number.strip()
            if not new_cabinet_number or len(new_cabinet_number) > 20:
                raise QueueCabinetManagementDomainError(
                    422, "Номер кабинета должен содержать от 1 до 20 символов"
                )

        try:
            # All command instances take queue rows first and in the same order.
            queues = self.repository.lock_daily_queues_for_cabinet_reassignment(
                queue_ids=queue_ids
            )
            queues_by_id = {queue.id: queue for queue in queues}
            if len(queues_by_id) != len(queue_ids):
                raise QueueCabinetManagementDomainError(
                    404, "Одна или несколько очередей не найдены"
                )

            # Called/clinical transitions and ServiceExecution creation lock the
            # queue-entry row. Taking every existing entry after its parent queue
            # serializes those transitions and FK-backed execution inserts here.
            self.repository.lock_queue_entries_for_cabinet_reassignment(
                queue_ids=queue_ids
            )

            clinic_day = clinic_today(self.db)
            if any(queue.day != clinic_day for queue in queues):
                raise QueueCabinetManagementDomainError(
                    409, "Изменять можно только очереди текущего дня клиники"
                )

            targets_by_id = {target["queue_id"]: target for target in targets}
            owners_by_id: dict[int, dict[str, Any]] = {}
            for queue_id in queue_ids:
                queue = queues_by_id[queue_id]
                target = targets_by_id[queue_id]
                owner = self._preview_owner(queue)
                owners_by_id[queue_id] = owner
                if (
                    owner["owner_type"] != target["expected_owner_type"]
                    or owner["owner_id"] != target["expected_owner_id"]
                    or queue.cabinet_number != target["expected_cabinet_number"]
                ):
                    logger.warning(
                        "Cabinet reassignment rejected stale target queue_id=%s request_id=%s",
                        queue_id,
                        request_id,
                    )
                    raise QueueCabinetManagementDomainError(
                        409,
                        "Состояние очереди изменилось после preview; обновите данные",
                    )

            changed_ids = [
                queue_id
                for queue_id in queue_ids
                if queues_by_id[queue_id].cabinet_number != new_cabinet_number
            ]
            blocking_reasons_by_queue = self._blocking_reasons_by_queue(
                queue_ids=changed_ids
            )
            blocked_ids = [
                queue_id
                for queue_id, reasons in blocking_reasons_by_queue.items()
                if reasons
            ]
            if blocked_ids:
                logger.warning(
                    "Cabinet reassignment rejected active queue state queue_ids=%s request_id=%s",
                    blocked_ids,
                    request_id,
                )
                raise QueueCabinetManagementDomainError(
                    409,
                    "Перенос заблокирован: по одной или нескольким очередям уже вызван пациент или идёт обслуживание",
                )

            changed_set = set(changed_ids)
            for queue_id in sorted(changed_ids):
                queue = queues_by_id[queue_id]
                owner = owners_by_id[queue_id]
                old_cabinet_number = queue.cabinet_number
                queue.cabinet_number = new_cabinet_number
                self.repository.add_cabinet_reassignment_audit(
                    queue_id=queue_id,
                    actor_user_id=actor_user_id,
                    actor_role=actor_role,
                    reason_code=reason_code,
                    payload={
                        "queue_day": queue.day.isoformat(),
                        "owner_type": owner["owner_type"],
                        "owner_id": owner["owner_id"],
                        "old_cabinet_number": old_cabinet_number,
                        "new_cabinet_number": new_cabinet_number,
                        "reason_code": reason_code,
                        "request_id": request_id,
                    },
                )

            result = {
                "clinic_day": clinic_day,
                "changed_queue_ids": [
                    queue_id for queue_id in queue_ids if queue_id in changed_set
                ],
                "unchanged_queue_ids": [
                    queue_id for queue_id in queue_ids if queue_id not in changed_set
                ],
                "applied_at": datetime.now(UTC),
            }
            if changed_ids:
                self.repository.commit()
            else:
                self.repository.rollback()
            if changed_ids:
                logger.info(
                    "Cabinet reassignment applied actor_id=%s queue_ids=%s reason_code=%s request_id=%s",
                    actor_user_id,
                    result["changed_queue_ids"],
                    reason_code,
                    request_id,
                )
            return result
        except QueueCabinetManagementDomainError:
            self.repository.rollback()
            raise
        except Exception as exc:
            self.repository.rollback()
            logger.error(
                "Cabinet reassignment failed actor_id=%s queue_ids=%s request_id=%s error_type=%s",
                actor_user_id,
                queue_ids,
                request_id,
                type(exc).__name__,
            )
            raise QueueCabinetManagementDomainError(
                500, "Не удалось изменить кабинеты; данные не сохранены"
            ) from exc

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
        if "cabinet_number" in cabinet_info:
            self._assign_queue_cabinet_number(queue, cabinet_info["cabinet_number"])
            updated = True
        if "cabinet_floor" in cabinet_info:
            queue.cabinet_floor = cabinet_info["cabinet_floor"]
            updated = True
        if "cabinet_building" in cabinet_info:
            queue.cabinet_building = cabinet_info["cabinet_building"]
            updated = True

        if updated:
            self.repository.commit()
            self.repository.refresh(queue)

        return {
            "success": True,
            "message": "Информация о кабинете обновлена",
            "queue_id": queue_id,
            "cabinet_info": self._build_queue_payload(queue),
            "updated_by": updated_by,
            "updated_at": datetime.now(UTC).isoformat(),
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
                errors.append(
                    {"queue_id": update["queue_id"], "error": "Очередь не найдена"}
                )
                continue

            cabinet_info = update["cabinet_info"]
            updated = False

            if "cabinet_number" in cabinet_info:
                try:
                    self._assign_queue_cabinet_number(
                        queue, cabinet_info["cabinet_number"]
                    )
                    updated = True
                except QueueCabinetManagementDomainError as exc:
                    errors.append({"queue_id": update["queue_id"], "error": exc.detail})
                    continue
            if "cabinet_floor" in cabinet_info:
                queue.cabinet_floor = cabinet_info["cabinet_floor"]
                updated = True
            if "cabinet_building" in cabinet_info:
                queue.cabinet_building = cabinet_info["cabinet_building"]
                updated = True

            if updated:
                updated_queues.append(
                    {
                        "queue_id": update["queue_id"],
                        "cabinet_info": self._build_queue_payload(queue),
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
            "updated_at": datetime.now(UTC).isoformat(),
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
            day_obj = clinic_today(self.db)

        queues = self.repository.list_queues_for_day(
            day_obj=day_obj,
            specialist_id=specialist_id,
        )

        updated_count = 0
        errors = []

        for queue in queues:
            try:
                # QD-2C (Codex round-16 P2): resource/bridged очередь —
                # кабинет принадлежит оси реестра (строка очереди /
                # default_cabinet), НЕ синтетику-врачу: sync не должен
                # затирать ресурсное назначение кабинета моста 0059
                # (retained specialist_id у моста — legacy-мост, не
                # владелец). Врач-очереди — байт-идентично.
                if getattr(queue, "queue_resource_id", None) is not None:
                    continue
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
            "synced_at": datetime.now(UTC).isoformat(),
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
            entry_count = self.repository.count_entries(queue_id=queue.id)
            cabinet_stats[queue.cabinet_number]["total_entries"] += entry_count

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
