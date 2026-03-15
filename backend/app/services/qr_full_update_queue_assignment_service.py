from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.service import Service
from app.services.queue_domain_service import QueueDomainService
from app.services.queue_service import queue_service
from app.services.queue_session import get_or_create_session_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QRFullUpdateCreateBranchHandoff:
    service_id: int
    service_name: str
    target_queue_id: int
    target_queue_tag: str | None
    queue_day: date
    current_queue_time: datetime
    create_entry_payload: dict[str, Any]


class QRFullUpdateQueueAssignmentService:
    """QR-local seam for full-update additional-service queue entry creation."""

    def __init__(
        self,
        db: Session,
        *,
        local_now_provider: Callable[[], datetime] | None = None,
        number_allocator: Callable[[int], int] | None = None,
        session_id_provider: Callable[[int, int, date], str] | None = None,
        boundary_allocator: QueueDomainService | None = None,
    ) -> None:
        self.db = db
        self._local_now_provider = (
            local_now_provider or (lambda: datetime.now(ZoneInfo("Asia/Tashkent")))
        )
        self._number_allocator = number_allocator or self._allocate_next_number
        self._session_id_provider = session_id_provider or self._get_session_id
        self._boundary_allocator = boundary_allocator or QueueDomainService(db)

    def prepare_create_branch_handoffs(
        self,
        *,
        entry: OnlineQueueEntry,
        request_services: Sequence[dict[str, Any]],
        new_service_ids: Sequence[int],
        discount_mode: str | None,
        all_free: bool,
        log_prefix: str,
    ) -> list[QRFullUpdateCreateBranchHandoff]:
        if not new_service_ids:
            return []

        entry_queue = self._get_entry_queue(entry)
        current_queue_time = self._local_now_provider()
        handoffs: list[QRFullUpdateCreateBranchHandoff] = []

        logger.info(
            "%s Creating %d Independent Queue Entries with current time: %s",
            log_prefix,
            len(new_service_ids),
            current_queue_time,
        )

        for new_service_id in new_service_ids:
            new_service = (
                self.db.query(Service).filter(Service.id == new_service_id).first()
            )
            if not new_service:
                continue

            target_queue = self._resolve_target_queue(
                entry_queue=entry_queue,
                new_service=new_service,
                log_prefix=log_prefix,
            )
            quantity = self._get_quantity(
                request_services=request_services,
                service_id=new_service_id,
            )
            item_price = self._calculate_item_price(
                service=new_service,
                quantity=quantity,
                discount_mode=discount_mode,
                all_free=all_free,
            )

            services_json = json.dumps(
                [
                    {
                        "service_id": new_service.id,
                        "name": new_service.name,
                        "code": new_service.code or "UNKNOWN",
                        "quantity": quantity,
                        "price": int(item_price),
                        "queue_time": current_queue_time.isoformat(),
                        "cancelled": False,
                    }
                ],
                ensure_ascii=False,
            )
            service_codes_json = json.dumps(
                [new_service.code or "UNKNOWN"],
                ensure_ascii=False,
            )

            handoffs.append(
                QRFullUpdateCreateBranchHandoff(
                    service_id=new_service_id,
                    service_name=new_service.name,
                    target_queue_id=target_queue.id,
                    target_queue_tag=target_queue.queue_tag,
                    queue_day=entry_queue.day,
                    current_queue_time=current_queue_time,
                    create_entry_payload={
                        "patient_id": entry.patient_id,
                        "patient_name": entry.patient_name,
                        "phone": entry.phone,
                        "birth_year": entry.birth_year,
                        "address": entry.address,
                        "status": "waiting",
                        "source": entry.source or "online",
                        "discount_mode": discount_mode or entry.discount_mode,
                        "visit_id": None,
                        "total_amount": int(item_price),
                        "services": services_json,
                        "service_codes": service_codes_json,
                    },
                )
            )

        return handoffs

    def materialize_create_branch_handoffs(
        self,
        handoffs: Sequence[QRFullUpdateCreateBranchHandoff],
        *,
        log_prefix: str,
    ) -> list[OnlineQueueEntry]:
        created_entries: list[OnlineQueueEntry] = []
        for handoff in handoffs:
            created_entries.append(
                self._materialize_create_branch_handoff(
                    handoff,
                    log_prefix=log_prefix,
                )
            )
        return created_entries

    def _resolve_target_queue(
        self,
        *,
        entry_queue: DailyQueue,
        new_service: Service,
        log_prefix: str,
    ) -> DailyQueue:
        if not new_service.queue_tag:
            return entry_queue

        candidate_queue = (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.day == entry_queue.day,
                DailyQueue.queue_tag == new_service.queue_tag,
                DailyQueue.active.is_(True),
            )
            .first()
        )
        if candidate_queue:
            logger.info(
                "%s Service %s -> queue %s (ID=%d)",
                log_prefix,
                new_service.name,
                new_service.queue_tag,
                candidate_queue.id,
            )
            return candidate_queue

        logger.warning(
            "%s DailyQueue for queue_tag=%s not found, creating...",
            log_prefix,
            new_service.queue_tag,
        )
        new_queue = queue_service.get_or_create_daily_queue(
            self.db,
            day=entry_queue.day,
            specialist_id=entry_queue.specialist_id,
            queue_tag=new_service.queue_tag,
        )
        logger.info(
            "%s Created DailyQueue for %s (ID=%d)",
            log_prefix,
            new_service.queue_tag,
            new_queue.id,
        )
        return new_queue

    def _materialize_create_branch_handoff(
        self,
        handoff: QRFullUpdateCreateBranchHandoff,
        *,
        log_prefix: str,
    ) -> OnlineQueueEntry:
        payload = handoff.create_entry_payload
        next_number = self._number_allocator(handoff.target_queue_id)
        session_id = self._session_id_provider(
            payload["patient_id"],
            handoff.target_queue_id,
            handoff.queue_day,
        )
        create_entry_kwargs = self.build_create_entry_kwargs(
            handoff,
            commit=False,
        )
        create_entry_kwargs.update(
            {
                "number": next_number,
                "session_id": session_id,
            }
        )
        new_entry = self._boundary_allocator.allocate_ticket(
            allocation_mode="create_entry",
            **create_entry_kwargs,
        )

        logger.info(
            "%s Created Independent Entry for %s (ID=%d), queue_id=%d, number=%d, time=%s",
            log_prefix,
            handoff.service_name,
            handoff.service_id,
            handoff.target_queue_id,
            next_number,
            handoff.current_queue_time,
        )
        return new_entry

    def build_create_entry_kwargs(
        self,
        handoff: QRFullUpdateCreateBranchHandoff,
        *,
        commit: bool = False,
    ) -> dict[str, Any]:
        """Build a boundary-compatible create-entry payload without migrating callers."""

        payload = handoff.create_entry_payload
        return {
            "queue_id": handoff.target_queue_id,
            "patient_id": payload["patient_id"],
            "patient_name": payload["patient_name"],
            "phone": payload["phone"],
            "birth_year": payload["birth_year"],
            "address": payload["address"],
            "visit_id": payload["visit_id"],
            "discount_mode": payload["discount_mode"],
            "services": payload["services"],
            "service_codes": payload["service_codes"],
            "total_amount": payload["total_amount"],
            "source": payload["source"],
            "status": payload["status"],
            "queue_time": handoff.current_queue_time,
            "commit": commit,
        }

    def _allocate_next_number(self, queue_id: int) -> int:
        return self.db.execute(
            text(
                "SELECT COALESCE(MAX(number), 0) + 1 FROM queue_entries WHERE queue_id = :qid"
            ),
            {"qid": queue_id},
        ).scalar()

    def _get_session_id(self, patient_id: int, queue_id: int, queue_day: date) -> str:
        return get_or_create_session_id(self.db, patient_id, queue_id, queue_day)

    def _get_entry_queue(self, entry: OnlineQueueEntry) -> DailyQueue:
        entry_queue = getattr(entry, "queue", None)
        if entry_queue is not None:
            return entry_queue

        queue = self.db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
        if queue is None:
            raise ValueError(f"DailyQueue {entry.queue_id} not found")
        return queue

    @staticmethod
    def _get_quantity(
        *,
        request_services: Sequence[dict[str, Any]],
        service_id: int,
    ) -> int:
        service_item = next(
            (item for item in request_services if item["service_id"] == service_id),
            None,
        )
        return service_item.get("quantity", 1) if service_item else 1

    @staticmethod
    def _calculate_item_price(
        *,
        service: Service,
        quantity: int,
        discount_mode: str | None,
        all_free: bool,
    ) -> Any:
        item_price = service.price * quantity
        if service.is_consultation and discount_mode in ["repeat", "benefit"]:
            item_price = 0
        if all_free:
            item_price = 0
        return item_price
