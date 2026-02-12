"""Business logic for registrar batch queue creation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.repositories.queue_batch_repository import QueueBatchRepository
from app.services.queue_service import queue_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueueBatchServiceItem:
    specialist_id: int
    service_id: int
    quantity: int = 1


@dataclass(frozen=True)
class QueueBatchEntryResult:
    specialist_id: int
    queue_id: int
    number: int
    queue_time: str


@dataclass(frozen=True)
class QueueBatchResult:
    success: bool
    entries: list[QueueBatchEntryResult]
    message: str


@dataclass(frozen=True)
class QueueBatchDomainError(Exception):
    status_code: int
    detail: str


class QueueBatchService:
    """Service layer: validation + domain rules, no HTTP concerns."""

    def __init__(self, db: Session):
        self.repository = QueueBatchRepository(db)

    def create_entries(
        self,
        *,
        patient_id: int,
        source: Literal["online", "desk", "morning_assignment"],
        services: list[QueueBatchServiceItem],
    ) -> QueueBatchResult:
        try:
            patient = self.repository.get_patient(patient_id)
            if not patient:
                raise QueueBatchDomainError(
                    status_code=404,
                    detail=f"Пациент с ID {patient_id} не найден",
                )

            today = date.today()
            current_time = datetime.now(ZoneInfo("Asia/Tashkent"))

            services_by_specialist: dict[int, list[QueueBatchServiceItem]] = {}
            for service_item in services:
                service = self.repository.get_active_service(service_item.service_id)
                if not service:
                    raise QueueBatchDomainError(
                        status_code=404,
                        detail=f"Услуга с ID {service_item.service_id} не найдена",
                    )

                specialist_user_id, converted = self.repository.resolve_specialist_user_id(
                    service_item.specialist_id
                )
                if specialist_user_id is None:
                    raise QueueBatchDomainError(
                        status_code=404,
                        detail=f"Специалист с ID {service_item.specialist_id} не найден",
                    )

                if converted:
                    logger.info(
                        "[QueueBatchService] Converted doctor_id=%s to user_id=%s",
                        service_item.specialist_id,
                        specialist_user_id,
                    )

                services_by_specialist.setdefault(specialist_user_id, []).append(
                    service_item
                )

            created_entries: list[QueueBatchEntryResult] = []
            existing_entries_count = 0
            patient_name = (
                patient.short_name()
                if hasattr(patient, "short_name")
                else f"{patient.last_name} {patient.first_name}"
            )
            patient_phone = patient.phone or None

            for specialist_id in services_by_specialist:
                existing_entry = self.repository.find_existing_active_entry(
                    specialist_id=specialist_id,
                    day=today,
                    patient_id=patient_id,
                )
                if existing_entry:
                    existing_entries_count += 1
                    created_entries.append(
                        QueueBatchEntryResult(
                            specialist_id=specialist_id,
                            queue_id=existing_entry.queue_id,
                            number=existing_entry.number,
                            queue_time=(
                                existing_entry.queue_time.isoformat()
                                if existing_entry.queue_time
                                else current_time.isoformat()
                            ),
                        )
                    )
                    continue

                daily_queue = self.repository.get_or_create_daily_queue(
                    day=today,
                    specialist_id=specialist_id,
                )

                try:
                    queue_entry = queue_service.create_queue_entry(
                        db=self.repository.db,
                        daily_queue=daily_queue,
                        patient_id=patient_id,
                        patient_name=patient_name,
                        phone=patient_phone,
                        source=source,
                        queue_time=current_time,
                        commit=False,
                    )
                except ValueError as exc:
                    raise QueueBatchDomainError(
                        status_code=400,
                        detail=(
                            f"Ошибка создания записи для специалиста {specialist_id}: {exc}"
                        ),
                    ) from exc

                created_entries.append(
                    QueueBatchEntryResult(
                        specialist_id=specialist_id,
                        queue_id=queue_entry.queue_id,
                        number=queue_entry.number,
                        queue_time=(
                            queue_entry.queue_time.isoformat()
                            if queue_entry.queue_time
                            else current_time.isoformat()
                        ),
                    )
                )

            self.repository.commit()

            entries_count = len(created_entries)
            message = (
                f"Создано {entries_count} "
                f"{'записей' if entries_count != 1 else 'запись'} в очереди"
            )
            if existing_entries_count:
                message += (
                    f", {existing_entries_count} "
                    f"{'запись уже существовала' if existing_entries_count == 1 else 'записей уже существовало'}"
                )

            return QueueBatchResult(
                success=True,
                entries=created_entries,
                message=message,
            )
        except QueueBatchDomainError:
            self.repository.rollback()
            raise
        except Exception as exc:
            self.repository.rollback()
            logger.error(
                "[QueueBatchService] Unexpected error during batch creation: %s",
                exc,
                exc_info=True,
            )
            raise QueueBatchDomainError(
                status_code=500,
                detail=f"Ошибка массового создания записей в очереди: {exc}",
            ) from exc

