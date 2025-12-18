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
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.visit import Visit

logger = logging.getLogger(__name__)


# ============================================================================
# SCHEMAS
# ============================================================================

class EntryAction(BaseModel):
    """Действие над одной записью в batch-операции"""
    id: Optional[int] = None  # None для создания новой
    action: Literal["update", "cancel", "create"]
    
    # Для update/create:
    service_id: Optional[int] = None
    service_code: Optional[str] = None
    doctor_id: Optional[int] = None
    specialty: Optional[str] = None
    status: Optional[str] = None
    
    # Для cancel:
    reason: Optional[str] = None


class CommonUpdates(BaseModel):
    """Общие обновления для всех записей пациента"""
    payment_type: Optional[str] = None
    discount_mode: Optional[str] = None
    approval_status: Optional[str] = None
    notes: Optional[str] = None


class BatchUpdateRequest(BaseModel):
    """Запрос на batch-обновление записей пациента"""
    entries: List[EntryAction] = Field(default_factory=list)
    common_updates: Optional[CommonUpdates] = None


class EntryResult(BaseModel):
    """Результат операции над одной записью"""
    id: int
    status: Literal["updated", "cancelled", "created", "error"]
    error: Optional[str] = None


class BatchUpdateResponse(BaseModel):
    """Ответ на batch-обновление"""
    success: bool
    patient_id: int
    date: str
    updated_entries: List[EntryResult]
    aggregated_row: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


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
    ) -> Dict[str, Any]:
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
        results: List[EntryResult] = []
        
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
        from app.services.queue_service import QueueService
        
        # Используем существующий QueueService для создания
        queue_service = QueueService(self.db)
        
        try:
            result = queue_service.add_to_queue(
                patient_id=patient_id,
                specialty=action.specialty or "general",
                service_id=action.service_id,
                service_code=action.service_code,
                source="batch_update"
            )
            
            return EntryResult(
                id=result.get("entry_id", 0),
                status="created"
            )
        except Exception as e:
            logger.error(f"Failed to create entry: {e}")
            return EntryResult(
                id=0,
                status="error",
                error=str(e)
            )
    
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
        online_entries: List[OnlineQueueEntry],
        visits: List[Visit],
        patient_id: int
    ) -> Dict[str, Any]:
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
            if entry.service_code:
                services.append(entry.service_code)
            queue_numbers.append({
                "id": entry.id,
                "number": entry.number,
                "queue_tag": entry.queue_tag,
                "status": entry.status
            })
        
        # Собираем данные из Visit
        for visit in visits:
            if hasattr(visit, 'service') and visit.service:
                services.append(visit.service.code if hasattr(visit.service, 'code') else str(visit.service_id))
            if hasattr(visit, 'cost') and visit.cost:
                total_cost += visit.cost
        
        return {
            "patient_id": patient_id,
            "patient_fio": patient.fio if patient else "",
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
