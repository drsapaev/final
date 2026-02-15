"""Service layer for appointments endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.crud.appointment import appointment as appointment_crud
from app.models import appointment as appointment_models
from app.models.patient import Patient
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.setting import Setting
from app.models.visit import Visit, VisitService
from app.repositories.appointments_api_repository import AppointmentsApiRepository
from app.schemas import appointment as appointment_schemas
from app.services.service_mapping import get_service_code


class AppointmentsApiService:
    """Builds payloads for appointments API endpoints."""

    def __init__(
        self,
        db: Session,
        repository: AppointmentsApiRepository | None = None,
    ):
        self.repository = repository or AppointmentsApiRepository(db)

    def list_appointments(
        self,
        *,
        skip: int,
        limit: int,
        patient_id: int | None,
        doctor_id: int | None,
        department: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> list[dict[str, Any]]:
        appointments = appointment_crud.get_appointments(
            self.repository.db,
            skip=skip,
            limit=limit,
            patient_id=patient_id,
            doctor_id=doctor_id,
            department=department,
            date_from=date_from,
            date_to=date_to,
        )

        result = []
        for apt in appointments:
            patient_name = None
            if apt.patient_id:
                patient = self.repository.db.query(Patient).filter(Patient.id == apt.patient_id).first()
                patient_name = patient.short_name() if patient else f"Пациент #{apt.patient_id}"

            services_with_names = []
            if apt.services and isinstance(apt.services, list):
                for service_item in apt.services:
                    if isinstance(service_item, str):
                        service = (
                            self.repository.db.query(Service)
                            .filter((Service.code == service_item) | (Service.service_code == service_item))
                            .first()
                        )
                        services_with_names.append(service.name if service else service_item)
                    elif isinstance(service_item, dict):
                        if "name" in service_item:
                            services_with_names.append(service_item["name"])
                        elif "code" in service_item:
                            service = (
                                self.repository.db.query(Service)
                                .filter(
                                    (Service.code == service_item["code"])
                                    | (Service.service_code == service_item["code"])
                                )
                                .first()
                            )
                            services_with_names.append(
                                service.name if service else service_item.get("code", "Услуга")
                            )
                        else:
                            services_with_names.append(str(service_item))
                    else:
                        services_with_names.append(str(service_item))

            apt_dict = appointment_schemas.Appointment.model_validate(apt).model_dump()
            apt_dict["patient_name"] = patient_name
            if services_with_names:
                apt_dict["services"] = services_with_names
            result.append(apt_dict)

        return result

    def upsert_queue_setting(self, *, key: str, value: str) -> None:
        now = datetime.utcnow()
        row = self.repository.get_queue_setting(key=key)
        if row:
            row.value = value
            row.updated_at = now
            return
        row = Setting(category="queue", key=key, value=value, created_at=now, updated_at=now)
        self.repository.add(row)

    def commit(self) -> None:
        self.repository.commit()

    def get_pending_payments(
        self,
        *,
        skip: int,
        limit: int,
        date_from: str | None,
        date_to: str | None,
    ) -> list[dict[str, Any]]:
        from collections import defaultdict

        result = []

        appointments_query = self.repository.list_pending_appointments()

        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                appointments_query = appointments_query.filter(
                    appointment_models.Appointment.appointment_date >= from_date
                )
            except ValueError:
                pass

        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                appointments_query = appointments_query.filter(
                    appointment_models.Appointment.appointment_date <= to_date
                )
            except ValueError:
                pass

        appointments = appointments_query.order_by(appointment_models.Appointment.created_at.desc()).all()

        for apt in appointments:
            if apt.payment_amount and apt.status == "paid":
                continue

            patient_name = None
            patient_last_name = None
            patient_first_name = None
            if apt.patient_id:
                patient = self.repository.db.query(Patient).filter(Patient.id == apt.patient_id).first()
                if patient:
                    patient_name = patient.short_name()
                    patient_last_name = patient.last_name
                    patient_first_name = patient.first_name
                else:
                    patient_name = f"Пациент #{apt.patient_id}"

            services_codes: list[str] = []
            services_names: list[str] = []
            if apt.services and isinstance(apt.services, list):
                for service_item in apt.services:
                    if isinstance(service_item, str):
                        service = (
                            self.repository.db.query(Service)
                            .filter((Service.code == service_item) | (Service.service_code == service_item))
                            .first()
                        )
                        if service:
                            service_code = get_service_code(service.id, self.repository.db) or service.code or service_item
                            services_codes.append(service_code)
                            services_names.append(service.name)
                        else:
                            services_codes.append(service_item)
                            services_names.append(service_item)
                    elif isinstance(service_item, dict):
                        code = (
                            service_item.get("code")
                            or service_item.get("service_code")
                            or str(service_item)
                        )
                        if "name" in service_item:
                            services_codes.append(code)
                            services_names.append(service_item["name"])
                        elif "code" in service_item:
                            service = (
                                self.repository.db.query(Service)
                                .filter(
                                    (Service.code == service_item["code"])
                                    | (Service.service_code == service_item["code"])
                                )
                                .first()
                            )
                            if service:
                                service_code = get_service_code(service.id, self.repository.db) or service.code or service_item["code"]
                                services_codes.append(service_code)
                                services_names.append(service.name)
                            else:
                                services_codes.append(code)
                                services_names.append(code)
                        else:
                            services_codes.append(str(service_item))
                            services_names.append(str(service_item))
                    else:
                        services_codes.append(str(service_item))
                        services_names.append(str(service_item))

            result.append(
                {
                    "id": int(apt.id),
                    "patient_id": int(apt.patient_id) if apt.patient_id else None,
                    "patient_name": str(patient_name) if patient_name else None,
                    "patient_last_name": str(patient_last_name) if patient_last_name else None,
                    "patient_first_name": str(patient_first_name) if patient_first_name else None,
                    "doctor_id": int(apt.doctor_id) if apt.doctor_id else None,
                    "department": str(apt.department) if apt.department else None,
                    "appointment_date": apt.appointment_date.isoformat() if apt.appointment_date else None,
                    "appointment_time": str(apt.appointment_time) if apt.appointment_time else None,
                    "status": str(apt.status),
                    "services": [str(s) for s in services_codes] if services_codes else [],
                    "services_names": [str(s) for s in services_names] if services_names else [],
                    "payment_amount": float(apt.payment_amount) if apt.payment_amount else None,
                    "created_at": apt.created_at.isoformat() if apt.created_at else None,
                    "record_type": "appointment",
                    "visit_ids": [],
                }
            )

        visits_query = self.repository.db.query(Visit).filter(Visit.discount_mode != "all_free")
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date <= to_date)
            except ValueError:
                pass

        visits = visits_query.order_by(Visit.created_at.desc()).all()
        visits_by_patient = defaultdict(
            lambda: {
                "visits": [],
                "patient_id": None,
                "patient_name": None,
                "patient_last_name": None,
                "patient_first_name": None,
                "visit_date": None,
                "created_at": None,
                "services_codes": [],
                "services_names": [],
                "total_amount": 0,
                "visit_ids": [],
            }
        )

        for visit in visits:
            paid_invoices = (
                self.repository.db.query(PaymentInvoiceVisit)
                .join(PaymentInvoice)
                .filter(
                    PaymentInvoiceVisit.visit_id == visit.id,
                    PaymentInvoice.status == "paid",
                )
                .first()
            )
            if paid_invoices:
                continue

            visit_date = visit.visit_date or (visit.created_at.date() if visit.created_at else None)
            group_key = (visit.patient_id, visit_date.isoformat() if visit_date else None)

            if group_key not in visits_by_patient:
                patient_name = None
                patient_last_name = None
                patient_first_name = None
                if visit.patient_id:
                    patient = self.repository.db.query(Patient).filter(Patient.id == visit.patient_id).first()
                    if patient:
                        patient_name = patient.short_name()
                        patient_last_name = patient.last_name
                        patient_first_name = patient.first_name
                    else:
                        patient_name = f"Пациент #{visit.patient_id}"

                visits_by_patient[group_key] = {
                    "visits": [],
                    "patient_id": visit.patient_id,
                    "patient_name": patient_name,
                    "patient_last_name": patient_last_name,
                    "patient_first_name": patient_first_name,
                    "visit_date": visit_date,
                    "created_at": visit.created_at,
                    "services_codes": [],
                    "services_names": [],
                    "total_amount": 0,
                    "visit_ids": [],
                }

            visits_by_patient[group_key]["visits"].append(visit)
            visits_by_patient[group_key]["visit_ids"].append(visit.id)
            if visit.created_at and (
                not visits_by_patient[group_key]["created_at"]
                or visit.created_at < visits_by_patient[group_key]["created_at"]
            ):
                visits_by_patient[group_key]["created_at"] = visit.created_at

        for group_data in visits_by_patient.values():
            all_services_codes = []
            all_services_names = []
            total_amount = 0

            for visit in group_data["visits"]:
                visit_services = (
                    self.repository.db.query(VisitService)
                    .filter(VisitService.visit_id == visit.id)
                    .all()
                )
                for vs in visit_services:
                    service_code = vs.code
                    if not service_code:
                        service = (
                            self.repository.db.query(Service)
                            .filter(Service.id == vs.service_id)
                            .first()
                        )
                        if service:
                            service_code = get_service_code(vs.service_id, self.repository.db) or service.code or f"S{vs.service_id}"
                    service_name = vs.name
                    if not service_name:
                        service = (
                            self.repository.db.query(Service)
                            .filter(Service.id == vs.service_id)
                            .first()
                        )
                        service_name = service.name if service else f"Услуга #{vs.service_id}"

                    if service_code not in all_services_codes:
                        all_services_codes.append(service_code or f"S{vs.service_id}")
                        all_services_names.append(service_name)
                    if vs.price:
                        total_amount += float(vs.price) * vs.qty

            if not group_data["visit_ids"]:
                continue

            result.append(
                {
                    "id": int(min(group_data["visit_ids"]) + 20000),
                    "patient_id": int(group_data["patient_id"]) if group_data["patient_id"] else None,
                    "patient_name": str(group_data["patient_name"]) if group_data["patient_name"] else None,
                    "patient_last_name": str(group_data["patient_last_name"]) if group_data["patient_last_name"] else None,
                    "patient_first_name": str(group_data["patient_first_name"]) if group_data["patient_first_name"] else None,
                    "doctor_id": None,
                    "department": None,
                    "appointment_date": group_data["visit_date"].isoformat() if group_data["visit_date"] else None,
                    "appointment_time": None,
                    "status": "pending",
                    "services": [str(s) for s in all_services_codes] if all_services_codes else [],
                    "services_names": [str(s) for s in all_services_names] if all_services_names else [],
                    "payment_amount": float(total_amount) if total_amount > 0 else None,
                    "created_at": group_data["created_at"].isoformat() if group_data["created_at"] else None,
                    "record_type": "visit",
                    "visit_ids": [int(v) for v in group_data["visit_ids"]] if group_data["visit_ids"] else [],
                }
            )

        result.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        paginated_result = result[skip : skip + limit]
        json_result = []
        for item in paginated_result:
            json_item = {}
            for key, value in item.items():
                if value is None or isinstance(value, (str, int, float, bool)):
                    json_item[key] = value
                elif isinstance(value, list):
                    json_item[key] = [
                        str(v) if not isinstance(v, (str, int, float, bool)) else v
                        for v in value
                    ]
                else:
                    json_item[key] = str(value)
            json_result.append(json_item)
        return json_result
