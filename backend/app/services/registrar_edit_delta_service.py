from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, attributes

from app.crud.patient import normalize_patient_name
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.queue_service import queue_service
from app.services.service_mapping import get_service_code, normalize_service_code

ACTIVE_APPEND_STATUSES = ("waiting", "called", "in_service", "diagnostics")


@dataclass(frozen=True)
class RegistrarEditDeltaItem:
    service_id: int
    quantity: int = 1
    specialist_id: int | None = None


class RegistrarEditDeltaService:
    """Append edit-mode service deltas without duplicating active queue rows."""

    def __init__(self, db: Session):
        self.db = db

    def apply(
        self,
        *,
        patient_id: int,
        services: list[RegistrarEditDeltaItem],
        target_date: date,
        payment_method: str,
        discount_mode: str,
        all_free: bool,
        patient_data: dict[str, Any] | None = None,
        existing_queue_entry_ids: list[int] | None = None,
        expected_entry_updated_at: dict[int, str] | None = None,
        current_user: User | None = None,
    ) -> dict[str, Any]:
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")

        # R-08 fix: optimistic locking — проверяем что existing entries не были
        # изменены другим пользователем с момента последнего чтения frontend'ом.
        if expected_entry_updated_at:
            self._assert_entries_not_concurrently_modified(
                expected_entry_updated_at
            )

        if patient_data:
            self._apply_patient_data(patient, patient_data)

        queue_entry_ids = set(existing_queue_entry_ids or [])
        queue_numbers: dict[int, list[dict[str, Any]]] = {}
        visit_delta_amounts: dict[int, Decimal] = {}
        updated_queue_entries: list[dict[str, Any]] = []
        created_visit_payloads: dict[int, dict[str, Any]] = {}

        for item in services:
            service = self.db.query(Service).filter(Service.id == item.service_id).first()
            if not service:
                raise ValueError(f"Service {item.service_id} not found")

            queue_tag = service.queue_tag or service.department_key
            if not queue_tag:
                raise ValueError(f"Service {service.id} has no queue tag")

            requested_qty = max(int(item.quantity or 1), 1)
            entry = self._find_active_entry(
                patient_id=patient_id,
                queue_tag=queue_tag,
                target_date=target_date,
                preferred_entry_ids=queue_entry_ids,
            )

            if entry:
                delta = self._append_to_existing_entry(
                    entry=entry,
                    patient=patient,
                    service=service,
                    requested_qty=requested_qty,
                    target_date=target_date,
                    specialist_id=item.specialist_id,
                    discount_mode=discount_mode,
                    all_free=all_free,
                    current_user=current_user,
                )
            else:
                delta = self._create_new_queue_entry(
                    patient=patient,
                    service=service,
                    requested_qty=requested_qty,
                    target_date=target_date,
                    specialist_id=item.specialist_id,
                    discount_mode=discount_mode,
                    all_free=all_free,
                    current_user=current_user,
                )

            if delta["delta_amount"] > 0 and delta["visit_id"]:
                visit_id = int(delta["visit_id"])
                visit_delta_amounts[visit_id] = (
                    visit_delta_amounts.get(visit_id, Decimal("0"))
                    + delta["delta_amount"]
                )
                created_visit_payloads.setdefault(
                    visit_id,
                    {
                        "visit_id": visit_id,
                        "patient_name": patient.short_name(),
                        "doctor_name": self._doctor_name(delta.get("doctor_id")),
                        "visit_date": target_date.isoformat(),
                        "visit_time": None,
                        "status": "open",
                        "department": service.department_key or service.queue_tag,
                        "services": [],
                        "confirmation_required": False,
                        "confirmation_token": None,
                    },
                )
                created_visit_payloads[visit_id]["services"].append(
                    self._service_response_payload(
                        service=service,
                        quantity=delta["delta_quantity"],
                        price=delta["unit_price"],
                    )
                )

            if delta["visit_id"]:
                queue_numbers.setdefault(int(delta["visit_id"]), [])
                assignment = {
                    "queue_tag": queue_tag,
                    "queue_id": delta["queue_id"],
                    "number": delta["number"],
                    "status": delta["queue_status"],
                    "queue_entry_id": delta["queue_entry_id"],
                }
                if assignment not in queue_numbers[int(delta["visit_id"])]:
                    queue_numbers[int(delta["visit_id"])].append(assignment)

            updated_queue_entries.append(
                {
                    "queue_entry_id": delta["queue_entry_id"],
                    "queue_id": delta["queue_id"],
                    "queue_tag": queue_tag,
                    "number": delta["number"],
                    "status": delta["queue_status"],
                    "visit_id": delta["visit_id"],
                    "delta_quantity": delta["delta_quantity"],
                    "delta_amount": delta["delta_amount"],
                }
            )

        total_amount = sum(visit_delta_amounts.values(), Decimal("0"))
        invoice = self._apply_invoice_delta(
            patient_id=patient_id,
            payment_method=payment_method,
            visit_delta_amounts=visit_delta_amounts,
            total_amount=total_amount,
        )

        self.db.commit()

        return {
            "success": True,
            "message": (
                "Запись обновлена. Добавленные услуги сохранены в существующей очереди."
                if total_amount > 0
                else "Запись обновлена. Новых платных услуг не добавлено."
            ),
            "invoice_id": invoice.id if invoice else None,
            "visit_ids": list(visit_delta_amounts.keys()),
            "total_amount": total_amount,
            "queue_numbers": queue_numbers,
            "print_tickets": [],
            "created_visits": list(created_visit_payloads.values()),
            "updated_queue_entries": updated_queue_entries,
        }

    def _assert_entries_not_concurrently_modified(
        self,
        expected_entry_updated_at: dict[int, str],
    ) -> None:
        """R-08 fix: optimistic locking via updated_at.

        Проверяет что ни одна из existing queue entries не была изменена
        другим пользователем с момента последнего чтения frontend'ом.

        Если хотя бы одна entry изменилась — raises ValueError (caller maps to 400).
        Это предотвращает silent data loss когда два регистратора одновременно
        редактируют одного пациента (добавляют услуги, меняют количество и т.д.).
        """

        entry_ids = list(expected_entry_updated_at.keys())
        if not entry_ids:
            return

        entries = (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id.in_(entry_ids))
            .all()
        )
        entries_by_id = {e.id: e for e in entries}

        for entry_id, expected_iso in expected_entry_updated_at.items():
            entry = entries_by_id.get(entry_id)
            if entry is None:
                # Entry уже удалена другим пользователем
                raise ValueError(
                    f"Запись очереди #{entry_id} была удалена другим пользователем. "
                    "Обновите страницу, чтобы получить актуальные данные."
                )

            try:
                expected_dt = datetime.fromisoformat(
                    expected_iso.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                # graceful degradation: не блокируем если не удалось распарсить
                continue

            # Нормализуем оба к timezone-aware UTC для сравнения
            if expected_dt.tzinfo is None:
                expected_dt = expected_dt.replace(tzinfo=UTC)

            actual_dt = entry.updated_at
            if actual_dt is None:
                continue
            if actual_dt.tzinfo is None:
                actual_dt = actual_dt.replace(tzinfo=UTC)

            # Допускаем 1 секунду разницы (clock skew, округление БД)
            if abs((actual_dt - expected_dt).total_seconds()) > 1:
                raise ValueError(
                    f"Запись очереди #{entry_id} была изменена другим пользователем. "
                    "Обновите страницу, чтобы получить актуальные данные."
                )

    def _apply_patient_data(self, patient: Patient, patient_data: dict[str, Any]) -> None:
        if patient_data.get("full_name"):
            names = normalize_patient_name(full_name=patient_data["full_name"])
            if names["last_name"]:
                patient.last_name = names["last_name"]
            if names["first_name"]:
                patient.first_name = names["first_name"]
            patient.middle_name = names["middle_name"]
        for attr in ("phone", "address"):
            if patient_data.get(attr) is not None:
                setattr(patient, attr, patient_data[attr])
        if patient_data.get("sex") is not None:
            patient.sex = patient_data["sex"]
        if patient_data.get("birth_date") is not None:
            patient.birth_date = patient_data["birth_date"]

    def _find_active_entry(
        self,
        *,
        patient_id: int,
        queue_tag: str,
        target_date: date,
        preferred_entry_ids: set[int],
    ) -> OnlineQueueEntry | None:
        entries = (
            self.db.query(OnlineQueueEntry)
            .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
            .filter(
                OnlineQueueEntry.patient_id == patient_id,
                OnlineQueueEntry.status.in_(ACTIVE_APPEND_STATUSES),
                DailyQueue.day == target_date,
                DailyQueue.queue_tag == queue_tag,
                DailyQueue.active.is_(True),
            )
            .order_by(OnlineQueueEntry.queue_time.asc(), OnlineQueueEntry.id.asc())
            .all()
        )
        if preferred_entry_ids:
            preferred = [entry for entry in entries if entry.id in preferred_entry_ids]
            if preferred:
                return preferred[0]
        return entries[0] if entries else None

    def _append_to_existing_entry(
        self,
        *,
        entry: OnlineQueueEntry,
        patient: Patient,
        service: Service,
        requested_qty: int,
        target_date: date,
        specialist_id: int | None,
        discount_mode: str,
        all_free: bool,
        current_user: User | None,
    ) -> dict[str, Any]:
        services = self._coerce_services(entry.services)
        existing_payload = self._find_service_payload(services, service)
        existing_qty = self._payload_quantity(existing_payload) if existing_payload else 0
        delta_qty = max(requested_qty - existing_qty, 0) if existing_payload else requested_qty
        unit_price = Decimal("0") if all_free else Decimal(str(service.price or 0))
        delta_amount = unit_price * Decimal(delta_qty)

        changed_at = queue_service.get_local_timestamp(self.db)

        if delta_qty > 0:
            if existing_payload:
                existing_payload["quantity"] = requested_qty
                existing_payload["qty"] = requested_qty
            else:
                services.append(
                    self._entry_service_payload(
                        service=service,
                        quantity=requested_qty,
                        unit_price=unit_price,
                    )
                )
            entry.services = services
            # R-41 fix: flag_modified для JSON column — без этого SQLAlchemy
            # не обнаруживает изменение mutable JSON field, update не persist'ится.
            # Silent data loss: пользователь меняет услуги, но БД не обновляется.
            attributes.flag_modified(entry, 'services')
            entry.service_codes = self._merged_service_codes(entry.service_codes, service)
            attributes.flag_modified(entry, 'service_codes')
            entry.total_amount = int(Decimal(str(entry.total_amount or 0)) + delta_amount)
            entry.updated_at = changed_at

        visit = self._ensure_entry_visit(
            entry=entry,
            patient=patient,
            service=service,
            target_date=target_date,
            specialist_id=specialist_id,
            discount_mode=discount_mode,
            current_user=current_user,
            create_only_if_needed=delta_qty > 0,
        )

        if visit and delta_qty > 0:
            visit.updated_at = changed_at
            self._append_visit_service(
                visit=visit,
                service=service,
                requested_qty=requested_qty,
                delta_qty=delta_qty,
                unit_price=unit_price,
            )

        return self._delta_result(
            entry=entry,
            service=service,
            visit=visit,
            delta_qty=delta_qty,
            unit_price=unit_price,
            delta_amount=delta_amount,
        )

    def _create_new_queue_entry(
        self,
        *,
        patient: Patient,
        service: Service,
        requested_qty: int,
        target_date: date,
        specialist_id: int | None,
        discount_mode: str,
        all_free: bool,
        current_user: User | None,
    ) -> dict[str, Any]:
        queue_tag = service.queue_tag or service.department_key
        daily_queue = self._resolve_daily_queue(
            service=service,
            specialist_id=specialist_id,
            queue_tag=queue_tag,
            target_date=target_date,
        )
        unit_price = Decimal("0") if all_free else Decimal(str(service.price or 0))
        delta_amount = unit_price * Decimal(requested_qty)
        visit = self._create_visit(
            patient=patient,
            service=service,
            target_date=target_date,
            specialist_id=specialist_id or daily_queue.specialist_id,
            discount_mode=discount_mode,
            current_user=current_user,
        )
        self._append_visit_service(
            visit=visit,
            service=service,
            requested_qty=requested_qty,
            delta_qty=requested_qty,
            unit_price=unit_price,
        )
        entry = queue_service.create_queue_entry(
            self.db,
            daily_queue=daily_queue,
            patient_id=patient.id,
            patient_name=patient.short_name(),
            phone=patient.phone,
            visit_id=visit.id,
            source="desk",
            status="waiting",
            services=[
                self._entry_service_payload(
                    service=service,
                    quantity=requested_qty,
                    unit_price=unit_price,
                )
            ],
            service_codes=self._merged_service_codes([], service),
            total_amount=int(delta_amount),
            auto_number=True,
            commit=False,
        )
        entry.updated_at = queue_service.get_local_timestamp(self.db)
        return self._delta_result(
            entry=entry,
            service=service,
            visit=visit,
            delta_qty=requested_qty,
            unit_price=unit_price,
            delta_amount=delta_amount,
        )

    def _ensure_entry_visit(
        self,
        *,
        entry: OnlineQueueEntry,
        patient: Patient,
        service: Service,
        target_date: date,
        specialist_id: int | None,
        discount_mode: str,
        current_user: User | None,
        create_only_if_needed: bool,
    ) -> Visit | None:
        if entry.visit_id:
            visit = self.db.query(Visit).filter(Visit.id == entry.visit_id).first()
            if visit:
                if visit.patient_id != patient.id:
                    raise ValueError(
                        "Queue entry visit does not belong to the requested patient"
                    )
                return visit
            if not create_only_if_needed:
                return None
        if not create_only_if_needed:
            return None
        visit = self._create_visit(
            patient=patient,
            service=service,
            target_date=target_date,
            specialist_id=specialist_id or entry.queue.specialist_id,
            discount_mode=discount_mode,
            current_user=current_user,
        )
        entry.visit_id = visit.id
        entry.updated_at = queue_service.get_local_timestamp(self.db)
        return visit

    def _create_visit(
        self,
        *,
        patient: Patient,
        service: Service,
        target_date: date,
        specialist_id: int | None,
        discount_mode: str,
        current_user: User | None,
    ) -> Visit:
        visit = Visit(
            patient_id=patient.id,
            doctor_id=specialist_id,
            visit_date=target_date,
            visit_time=None,
            department=service.department_key or service.queue_tag,
            discount_mode=discount_mode or "none",
            status="open",
            approval_status="approved",
            confirmed_at=datetime.now(UTC),
            confirmed_by=f"registrar_{current_user.id}" if current_user else None,
            source="desk",
        )
        self.db.add(visit)
        self.db.flush()
        return visit

    def _append_visit_service(
        self,
        *,
        visit: Visit,
        service: Service,
        requested_qty: int,
        delta_qty: int,
        unit_price: Decimal,
    ) -> None:
        existing = (
            self.db.query(VisitService)
            .filter(VisitService.visit_id == visit.id, VisitService.service_id == service.id)
            .first()
        )
        code = self._service_code(service)
        if existing:
            existing.qty = max(existing.qty or 0, requested_qty)
            existing.price = unit_price
            existing.code = code
            existing.name = service.name
            existing.currency = service.currency or "UZS"
            visit.updated_at = queue_service.get_local_timestamp(self.db)
            return
        visit.updated_at = queue_service.get_local_timestamp(self.db)
        self.db.add(
            VisitService(
                visit_id=visit.id,
                service_id=service.id,
                code=code,
                name=service.name,
                qty=delta_qty,
                price=unit_price,
                currency=service.currency or "UZS",
            )
        )

    def _resolve_daily_queue(
        self,
        *,
        service: Service,
        specialist_id: int | None,
        queue_tag: str | None,
        target_date: date,
    ) -> DailyQueue:
        existing = (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.day == target_date,
                DailyQueue.queue_tag == queue_tag,
                DailyQueue.active.is_(True),
            )
            .order_by(DailyQueue.id.asc())
            .first()
        )
        if existing:
            return existing

        resolved_specialist_id = specialist_id or service.doctor_id
        if not resolved_specialist_id:
            raise ValueError(
                f"No active queue exists for queue_tag={queue_tag}; specialist_id is required"
            )
        return queue_service.get_or_create_daily_queue(
            self.db,
            day=target_date,
            specialist_id=resolved_specialist_id,
            queue_tag=queue_tag,
            defaults={},
        )

    def _apply_invoice_delta(
        self,
        *,
        patient_id: int,
        payment_method: str,
        visit_delta_amounts: dict[int, Decimal],
        total_amount: Decimal,
    ) -> PaymentInvoice | None:
        if total_amount <= 0:
            return None
        visit_ids = list(visit_delta_amounts.keys())
        invoice = (
            self.db.query(PaymentInvoice)
            .join(PaymentInvoiceVisit, PaymentInvoiceVisit.invoice_id == PaymentInvoice.id)
            .filter(
                PaymentInvoice.patient_id == patient_id,
                PaymentInvoice.status == "pending",
                PaymentInvoiceVisit.visit_id.in_(visit_ids),
            )
            .order_by(PaymentInvoice.created_at.desc())
            .first()
        )
        if invoice:
            invoice.total_amount = Decimal(str(invoice.total_amount or 0)) + total_amount
        else:
            invoice = PaymentInvoice(
                patient_id=patient_id,
                total_amount=total_amount,
                currency="UZS",
                status="pending",
                payment_method=payment_method or "cash",
                notes="edit-delta",
            )
            self.db.add(invoice)
            self.db.flush()

        for visit_id, visit_amount in visit_delta_amounts.items():
            link = (
                self.db.query(PaymentInvoiceVisit)
                .filter(
                    PaymentInvoiceVisit.invoice_id == invoice.id,
                    PaymentInvoiceVisit.visit_id == visit_id,
                )
                .first()
            )
            if link:
                link.visit_amount = Decimal(str(link.visit_amount or 0)) + visit_amount
            else:
                self.db.add(
                    PaymentInvoiceVisit(
                        invoice_id=invoice.id,
                        visit_id=visit_id,
                        visit_amount=visit_amount,
                    )
                )
        return invoice

    def _delta_result(
        self,
        *,
        entry: OnlineQueueEntry,
        service: Service,
        visit: Visit | None,
        delta_qty: int,
        unit_price: Decimal,
        delta_amount: Decimal,
    ) -> dict[str, Any]:
        return {
            "queue_entry_id": entry.id,
            "queue_id": entry.queue_id,
            "number": entry.number,
            "queue_status": entry.status,
            "visit_id": visit.id if visit else entry.visit_id,
            "doctor_id": visit.doctor_id if visit else None,
            "service_id": service.id,
            "delta_quantity": delta_qty,
            "unit_price": unit_price,
            "delta_amount": delta_amount,
        }

    def _coerce_services(self, services_value: Any) -> list[dict[str, Any]]:
        if not services_value:
            return []
        if isinstance(services_value, list):
            return [
                dict(item) if isinstance(item, dict) else {"name": str(item)}
                for item in services_value
            ]
        if isinstance(services_value, str):
            try:
                parsed = json.loads(services_value)
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
                if isinstance(parsed, list):
                    return [
                        dict(item) if isinstance(item, dict) else {"name": str(item)}
                        for item in parsed
                    ]
            except Exception:
                return []
        return []

    def _find_service_payload(
        self, services: list[dict[str, Any]], service: Service
    ) -> dict[str, Any] | None:
        target_code = self._service_code(service)
        for payload in services:
            payload_id = payload.get("service_id") or payload.get("id")
            payload_code = payload.get("code") or payload.get("service_code")
            if payload_id == service.id:
                return payload
            if target_code and payload_code and normalize_service_code(payload_code) == target_code:
                return payload
        return None

    def _payload_quantity(self, payload: dict[str, Any] | None) -> int:
        if not payload:
            return 0
        try:
            return max(int(payload.get("quantity") or payload.get("qty") or 1), 1)
        except (TypeError, ValueError):
            return 1

    def _entry_service_payload(
        self,
        *,
        service: Service,
        quantity: int,
        unit_price: Decimal,
    ) -> dict[str, Any]:
        code = self._service_code(service)
        return {
            "id": service.id,
            "service_id": service.id,
            "code": code,
            "service_code": code,
            "name": service.name,
            "service_name": service.name,
            "quantity": quantity,
            "qty": quantity,
            "price": float(unit_price),
        }

    def _service_response_payload(
        self,
        *,
        service: Service,
        quantity: int,
        price: Decimal,
    ) -> dict[str, Any]:
        code = self._service_code(service)
        return {
            "name": service.name,
            "code": code,
            "quantity": quantity,
            "price": float(price),
        }

    def _merged_service_codes(self, existing_codes: Any, service: Service) -> list[str]:
        codes: list[str] = []
        if isinstance(existing_codes, list):
            codes.extend(str(code) for code in existing_codes if code)
        elif isinstance(existing_codes, str):
            try:
                parsed = json.loads(existing_codes)
                if isinstance(parsed, list):
                    codes.extend(str(code) for code in parsed if code)
            except Exception:
                if existing_codes:
                    codes.append(existing_codes)
        code = self._service_code(service)
        if code:
            codes.append(code)
        deduped: list[str] = []
        seen: set[str] = set()
        for code_value in codes:
            normalized = normalize_service_code(code_value)
            if normalized and normalized not in seen:
                deduped.append(normalized)
                seen.add(normalized)
        return deduped

    def _service_code(self, service: Service) -> str | None:
        raw = service.service_code or service.code or get_service_code(service.id, self.db)
        return normalize_service_code(raw) if raw else None

    def _doctor_name(self, doctor_id: int | None) -> str:
        if not doctor_id:
            return "Без врача"
        doctor = self.db.query(Doctor).filter(Doctor.id == doctor_id).first()
        if not doctor:
            return "Без врача"
        user = getattr(doctor, "user", None)
        if user:
            return user.full_name or user.username or "Без врача"
        return str(doctor.specialty or "Без врача")
