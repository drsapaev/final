"""
Сервис для batch-операций с записями пациента.

Решает проблему UI Row ↔ API Entry mismatch:
- UI показывает пациента как одну строку
- API оперирует множеством entries (OnlineQueueEntry, Visit, Appointment)

Этот сервис обеспечивает атомарные операции над всеми записями пациента за день.
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit
from app.services.queue_domain_service import QueueDomainService
from app.services.queue_service import get_queue_service
from app.services.service_mapping import (
    get_default_service_by_specialty,
    normalize_service_code,
    normalize_specialty,
)

logger = logging.getLogger(__name__)

_BATCH_CREATE_RESOURCE_MAPPING = {
    "ecg": "ecg_resource",
    "echokg": "ecg_resource",
    "lab": "lab_resource",
    "laboratory": "lab_resource",
    "general": "general_resource",
    "cardiology_common": "general_resource",
    "dermatology": "general_resource",
    "procedures": "general_resource",
}


# ============================================================================
# SCHEMAS
# ============================================================================

class EntryAction(BaseModel):
    """Действие над одной записью в batch-операции"""
    id: int | None = None  # None для создания новой
    action: Literal["update", "cancel", "create"]

    # Для update/create:
    service_id: int | None = None
    service_code: str | None = None
    doctor_id: int | None = None
    specialty: str | None = None
    status: str | None = None

    # Для cancel:
    reason: str | None = None


class CommonUpdates(BaseModel):
    """Общие обновления для всех записей пациента"""
    payment_type: str | None = None
    discount_mode: str | None = None
    approval_status: str | None = None
    notes: str | None = None


class BatchUpdateRequest(BaseModel):
    """Запрос на batch-обновление записей пациента"""
    entries: list[EntryAction] = Field(default_factory=list)
    common_updates: CommonUpdates | None = None


class EntryResult(BaseModel):
    """Результат операции над одной записью"""
    id: int
    status: Literal["updated", "cancelled", "created", "error"]
    error: str | None = None


class BatchUpdateResponse(BaseModel):
    """Ответ на batch-обновление"""
    success: bool
    patient_id: int
    date: str
    updated_entries: list[EntryResult]
    aggregated_row: dict[str, Any] | None = None
    error: str | None = None


# ============================================================================
# SERVICE
# ============================================================================

class BatchPatientService:
    """
    Сервис для атомарных batch-операций с записями пациента.

    Гарантирует:
    - Атомарность: все или ничего
    - Консистентность: проверка бизнес-правил
    - Изоляция: транзакционность
    """

    def __init__(self, db: Session):
        self.db = db

    def get_patient_entries_for_date(
        self,
        patient_id: int,
        target_date: date_type
    ) -> dict[str, Any]:
        """
        Получает все записи пациента на указанную дату.

        Returns:
            Dict с entries из разных источников:
            - online_queue_entries: List[OnlineQueueEntry]
            - visits: List[Visit]
            - aggregated: Dict с агрегированными данными
        """
        result = {
            "patient_id": patient_id,
            "date": str(target_date),
            "online_queue_entries": [],
            "visits": [],
            "aggregated": {}
        }

        # Получаем OnlineQueueEntry
        online_entries = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.patient_id == patient_id,
            OnlineQueueEntry.status.notin_(["cancelled", "completed"])
        ).join(
            DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id
        ).filter(
            DailyQueue.day == target_date
        ).all()

        result["online_queue_entries"] = online_entries

        # Получаем Visit записи
        visits = self.db.query(Visit).filter(
            Visit.patient_id == patient_id,
            Visit.visit_date == target_date,
            Visit.status.notin_(["cancelled"])
        ).all()

        result["visits"] = visits

        # Агрегируем данные
        result["aggregated"] = self._aggregate_entries(
            online_entries, visits, patient_id
        )

        return result

    def batch_update(
        self,
        patient_id: int,
        target_date: date_type,
        request: BatchUpdateRequest
    ) -> BatchUpdateResponse:
        """
        Выполняет batch-обновление записей пациента.

        Атомарная операция: если хотя бы одно действие не удалось,
        все изменения откатываются.
        """
        results: list[EntryResult] = []

        try:
            # Начинаем неявную транзакцию

            # Обрабатываем каждое действие
            for entry_action in request.entries:
                try:
                    if entry_action.action == "cancel":
                        result = self._cancel_entry(entry_action)
                    elif entry_action.action == "update":
                        result = self._update_entry(entry_action)
                    elif entry_action.action == "create":
                        result = self._create_entry(
                            patient_id, target_date, entry_action
                        )
                    else:
                        result = EntryResult(
                            id=entry_action.id or 0,
                            status="error",
                            error=f"Unknown action: {entry_action.action}"
                        )
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error processing entry {entry_action.id}: {e}")
                    results.append(EntryResult(
                        id=entry_action.id or 0,
                        status="error",
                        error=str(e)
                    ))

            # Применяем общие обновления ко всем оставшимся записям
            if request.common_updates:
                self._apply_common_updates(
                    patient_id, target_date, request.common_updates
                )

            # Проверяем, есть ли ошибки
            has_errors = any(r.status == "error" for r in results)

            if has_errors:
                # Откатываем транзакцию
                self.db.rollback()
                return BatchUpdateResponse(
                    success=False,
                    patient_id=patient_id,
                    date=str(target_date),
                    updated_entries=results,
                    error="One or more operations failed"
                )

            # Коммитим транзакцию
            self.db.commit()

            # Получаем обновлённые агрегированные данные
            updated_data = self.get_patient_entries_for_date(patient_id, target_date)

            return BatchUpdateResponse(
                success=True,
                patient_id=patient_id,
                date=str(target_date),
                updated_entries=results,
                aggregated_row=updated_data.get("aggregated")
            )

        except Exception as e:
            logger.error(f"Batch update failed for patient {patient_id}: {e}")
            self.db.rollback()
            return BatchUpdateResponse(
                success=False,
                patient_id=patient_id,
                date=str(target_date),
                updated_entries=results,
                error=str(e)
            )

    def _cancel_entry(self, action: EntryAction) -> EntryResult:
        """Отменяет запись"""
        if not action.id:
            return EntryResult(id=0, status="error", error="ID required for cancel")

        # Пробуем найти в OnlineQueueEntry
        entry = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id == action.id
        ).first()

        if entry:
            entry.status = "cancelled"
            entry.cancel_reason = action.reason
            return EntryResult(id=action.id, status="cancelled")

        # Пробуем найти в Visit
        visit = self.db.query(Visit).filter(
            Visit.id == action.id
        ).first()

        if visit:
            visit.status = "cancelled"
            return EntryResult(id=action.id, status="cancelled")

        return EntryResult(
            id=action.id,
            status="error",
            error="Entry not found"
        )

    def _update_entry(self, action: EntryAction) -> EntryResult:
        """Обновляет запись"""
        if not action.id:
            return EntryResult(id=0, status="error", error="ID required for update")

        # Пробуем найти в OnlineQueueEntry
        entry = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id == action.id
        ).first()

        if entry:
            if action.service_id:
                entry.service_id = action.service_id
            if action.service_code:
                entry.service_code = action.service_code
            if action.status:
                entry.status = action.status
            return EntryResult(id=action.id, status="updated")

        # Пробуем найти в Visit
        visit = self.db.query(Visit).filter(
            Visit.id == action.id
        ).first()

        if visit:
            if action.doctor_id:
                visit.doctor_id = action.doctor_id
            if action.status:
                visit.status = action.status
            return EntryResult(id=action.id, status="updated")

        return EntryResult(
            id=action.id,
            status="error",
            error="Entry not found"
        )

    def _create_entry(
        self,
        patient_id: int,
        target_date: date_type,
        action: EntryAction
    ) -> EntryResult:
        """Создаёт новую запись"""
        try:
            patient = self._get_patient_or_raise(patient_id)
            service = self._resolve_create_action_service(action)
            queue_tag = self._resolve_create_action_queue_tag(
                action=action,
                service=service,
            )
            daily_queue = self._resolve_create_action_daily_queue(
                action=action,
                target_date=target_date,
                queue_tag=queue_tag,
                service=service,
            )
            service_codes = self._build_create_action_service_codes(
                action=action,
                service=service,
            )
            services_payload = self._build_create_action_services_payload(
                service=service,
                service_codes=service_codes,
            )

            created_entry = QueueDomainService(self.db).allocate_ticket(
                allocation_mode="create_entry",
                daily_queue=daily_queue,
                patient_id=patient.id,
                patient_name=patient.short_name(),
                phone=patient.phone,
                source="batch_update",
                status="waiting",
                services=services_payload,
                service_codes=service_codes,
                auto_number=True,
                commit=False,
            )

            return EntryResult(
                id=created_entry.id,
                status="created"
            )
        except Exception as e:
            logger.error(f"Failed to create entry: {e}")
            return EntryResult(
                id=0,
                status="error",
                error=str(e)
            )

    def _get_patient_or_raise(self, patient_id: int) -> Patient:
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise ValueError(f"Пациент с ID {patient_id} не найден")
        return patient

    def _resolve_create_action_service(self, action: EntryAction) -> Service | None:
        service = None

        if action.service_id:
            service = (
                self.db.query(Service)
                .filter(Service.id == action.service_id)
                .first()
            )

        if service is None and action.service_code:
            normalized_code = normalize_service_code(action.service_code)
            candidate_codes = {
                code
                for code in {action.service_code, normalized_code}
                if code
            }
            service = (
                self.db.query(Service)
                .filter(
                    or_(
                        Service.service_code.in_(candidate_codes),
                        Service.code.in_(candidate_codes),
                    )
                )
                .first()
            )

        if service is None and action.specialty:
            default_service = get_default_service_by_specialty(self.db, action.specialty)
            if default_service:
                service = (
                    self.db.query(Service)
                    .filter(Service.id == default_service["id"])
                    .first()
                )

        return service

    def _resolve_create_action_queue_tag(
        self,
        *,
        action: EntryAction,
        service: Service | None,
    ) -> str:
        if service and service.queue_tag:
            return service.queue_tag

        normalized_specialty = normalize_specialty(action.specialty or "")
        if normalized_specialty:
            return normalized_specialty

        raise ValueError(
            "Не удалось определить queue_tag для create-action "
            "(ожидались service_id, service_code или specialty)"
        )

    def _resolve_create_action_daily_queue(
        self,
        *,
        action: EntryAction,
        target_date: date_type,
        queue_tag: str,
        service: Service | None,
    ) -> DailyQueue:
        queue_service = get_queue_service()

        explicit_specialist_id = action.doctor_id or getattr(service, "doctor_id", None)
        if explicit_specialist_id:
            return queue_service.get_or_create_daily_queue(
                self.db,
                day=target_date,
                specialist_id=explicit_specialist_id,
                queue_tag=queue_tag,
            )

        active_queues = (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.day == target_date,
                DailyQueue.queue_tag == queue_tag,
                DailyQueue.active == True,
            )
            .order_by(DailyQueue.id.asc())
            .all()
        )
        if len(active_queues) == 1:
            return active_queues[0]
        if len(active_queues) > 1:
            raise ValueError(
                "Неоднозначная очередь для create-action "
                f"(queue_tag={queue_tag}, date={target_date})"
            )

        resolved_specialist_id = self._resolve_create_action_specialist_id(
            action=action,
            queue_tag=queue_tag,
            service=service,
        )
        return queue_service.get_or_create_daily_queue(
            self.db,
            day=target_date,
            specialist_id=resolved_specialist_id,
            queue_tag=queue_tag,
        )

    def _resolve_create_action_specialist_id(
        self,
        *,
        action: EntryAction,
        queue_tag: str,
        service: Service | None,
    ) -> int:
        service_doctor_ids = [
            doctor_id
            for (doctor_id,) in (
                self.db.query(Service.doctor_id)
                .filter(
                    Service.active == True,
                    Service.queue_tag == queue_tag,
                    Service.doctor_id.isnot(None),
                )
                .distinct()
                .all()
            )
            if doctor_id is not None
        ]
        if len(service_doctor_ids) == 1:
            return int(service_doctor_ids[0])
        if len(service_doctor_ids) > 1:
            raise ValueError(
                "Неоднозначный владелец очереди по услугам "
                f"(queue_tag={queue_tag})"
            )

        resource_username = _BATCH_CREATE_RESOURCE_MAPPING.get(queue_tag)
        if resource_username:
            resource_doctor = (
                self.db.query(Doctor)
                .join(User, Doctor.user_id == User.id)
                .filter(
                    Doctor.active == True,
                    User.username == resource_username,
                    User.is_active == True,
                )
                .first()
            )
            if resource_doctor:
                return int(resource_doctor.id)

        specialty_candidates = {
            candidate.lower()
            for candidate in {
                action.specialty or "",
                normalize_specialty(action.specialty or ""),
                queue_tag,
                getattr(service, "queue_tag", "") or "",
            }
            if candidate
        }
        matching_doctors = [
            doctor
            for doctor in self.db.query(Doctor).filter(Doctor.active == True).all()
            if (doctor.specialty or "").strip().lower() in specialty_candidates
            or normalize_specialty((doctor.specialty or "").strip()) in specialty_candidates
        ]

        if len(matching_doctors) == 1:
            return int(matching_doctors[0].id)
        if len(matching_doctors) > 1:
            raise ValueError(
                "Неоднозначный врач для create-action "
                f"(queue_tag={queue_tag}, specialty={action.specialty})"
            )

        raise ValueError(
            "Не удалось определить владельца очереди для create-action "
            f"(queue_tag={queue_tag})"
        )

    def _build_create_action_service_codes(
        self,
        *,
        action: EntryAction,
        service: Service | None,
    ) -> list[str] | None:
        if action.service_code:
            normalized_code = normalize_service_code(action.service_code)
            return [normalized_code] if normalized_code else [action.service_code]

        if service:
            service_code = service.service_code or service.code
            if service_code:
                normalized_code = normalize_service_code(service_code)
                return [normalized_code] if normalized_code else [service_code]

        return None

    def _build_create_action_services_payload(
        self,
        *,
        service: Service | None,
        service_codes: list[str] | None,
    ) -> list[dict[str, Any]] | None:
        if not service:
            return None

        code = None
        if service_codes:
            code = service_codes[0]
        elif service.service_code or service.code:
            code = normalize_service_code(service.service_code or service.code)

        return [
            {
                "id": service.id,
                "code": code,
                "name": service.name,
                "price": float(service.price) if service.price else 0,
            }
        ]

    def _apply_common_updates(
        self,
        patient_id: int,
        target_date: date_type,
        updates: CommonUpdates
    ) -> None:
        """Применяет общие обновления ко всем записям пациента за день"""
        # Обновляем OnlineQueueEntry
        entries = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.patient_id == patient_id,
            OnlineQueueEntry.status.notin_(["cancelled", "completed"])
        ).join(
            DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id
        ).filter(
            DailyQueue.day == target_date
        ).all()

        for entry in entries:
            if updates.notes:
                entry.notes = updates.notes

        # Обновляем Visit записи
        visits = self.db.query(Visit).filter(
            Visit.patient_id == patient_id,
            Visit.visit_date == target_date,
            Visit.status.notin_(["cancelled"])
        ).all()

        for visit in visits:
            if updates.payment_type:
                visit.payment_type = updates.payment_type
            if updates.discount_mode:
                visit.discount_mode = updates.discount_mode
            if updates.notes:
                visit.notes = updates.notes

    def _aggregate_entries(
        self,
        online_entries: list[OnlineQueueEntry],
        visits: list[Visit],
        patient_id: int
    ) -> dict[str, Any]:
        """Агрегирует данные из разных источников в единую структуру"""
        # Получаем данные пациента
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id
        ).first()

        services = []
        queue_numbers = []
        total_cost = 0

        # Собираем данные из OnlineQueueEntry
        for entry in online_entries:
            legacy_service_code = getattr(entry, "service_code", None)
            if legacy_service_code:
                services.append(legacy_service_code)
            elif entry.service_codes:
                services.extend(code for code in entry.service_codes if code)

            queue_tag = getattr(entry, "queue_tag", None)
            if queue_tag is None and getattr(entry, "queue", None):
                queue_tag = entry.queue.queue_tag
            queue_numbers.append({
                "id": entry.id,
                "number": entry.number,
                "queue_tag": queue_tag,
                "status": entry.status,
                "queue_time": entry.queue_time.isoformat() if entry.queue_time else None  # ⭐ FIX 13
            })

        # Собираем данные из Visit
        for visit in visits:
            if hasattr(visit, 'service') and visit.service:
                services.append(visit.service.code if hasattr(visit.service, 'code') else str(visit.service_id))
            if hasattr(visit, 'cost') and visit.cost:
                total_cost += visit.cost

        return {
            "patient_id": patient_id,
            "patient_fio": (
                patient.short_name()
                if patient
                else ""
            ),
            "patient_phone": patient.phone if patient else "",
            "services": list(set(services)),  # Unique
            "queue_numbers": queue_numbers,
            "total_cost": total_cost,
            "entry_count": len(online_entries) + len(visits)
        }


# Factory function
def get_batch_patient_service(db: Session) -> BatchPatientService:
    """Получить экземпляр BatchPatientService"""
    return BatchPatientService(db)
