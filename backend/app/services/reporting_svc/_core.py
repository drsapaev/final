"""Core mixin for ReportingService. Split from reporting_service.py."""
from __future__ import annotations
from app.services.reporting_svc._base import *  # noqa: F401, F403
from app.services.reporting_svc._base import ReportingServiceMixinBase


class CoreMixin(ReportingServiceMixinBase):
    """Core methods."""

    def __init__(self, db: Session):
        self.db = db
        self.reports_dir = "reports"
        os.makedirs(self.reports_dir, exist_ok=True)

    @staticmethod


    def _as_float(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0


    def _visit_service_amount(self, visit: Visit) -> float:
        total = 0.0
        for visit_service in getattr(visit, "services", None) or []:
            quantity = getattr(
                visit_service,
                "qty",
                getattr(visit_service, "quantity", 1),
            )
            try:
                quantity = int(quantity or 1)
            except (TypeError, ValueError):
                quantity = 1
            total += self._as_float(getattr(visit_service, "price", 0)) * quantity
        return total


    def _visit_invoice_links(self, visit: Visit) -> list[Any]:
        return list(getattr(visit, "invoices", None) or [])


    def _visit_total_amount(self, visit: Visit) -> float:
        invoice_links = self._visit_invoice_links(visit)
        if invoice_links:
            return sum(
                self._as_float(getattr(invoice_link, "visit_amount", 0))
                for invoice_link in invoice_links
            )
        return self._visit_service_amount(visit)


    def _visit_payment_status(self, visit: Visit) -> str:
        statuses = [
            getattr(getattr(invoice_link, "invoice", None), "status", None)
            for invoice_link in self._visit_invoice_links(visit)
        ]
        if "paid" in statuses:
            return "paid"
        if "processing" in statuses:
            return "processing"
        if "pending" in statuses:
            return "pending"
        if getattr(visit, "discount_mode", None) == "all_free":
            return "paid"
        return "unpaid"


    def _visit_payment_method(self, visit: Visit) -> str:
        if getattr(visit, "discount_mode", None) == "all_free":
            return "free"
        for invoice_link in self._visit_invoice_links(visit):
            invoice = getattr(invoice_link, "invoice", None)
            if getattr(invoice, "status", None) != "paid":
                continue
            method = (getattr(invoice, "payment_method", None) or "").lower()
            provider = (getattr(invoice, "provider", None) or "").lower()
            if method in {"cash", "card", "free"}:
                return method
            if method in {"online", "click", "payme"} or provider in {
                "click",
                "payme",
            }:
                return "online"
        return "card"

    # ===================== ОСНОВНЫЕ ОТЧЕТЫ =====================


    def generate_patient_report(
        self,
        start_date: date = None,
        end_date: date = None,
        department: str = None,
        format: str = "json",
    ) -> dict[str, Any]:
        """Генерирует отчет по пациентам"""
        try:
            query = self.db.query(Patient)

            # Фильтры по датам
            if start_date:
                query = query.filter(Patient.created_at >= start_date)
            if end_date:
                query = query.filter(Patient.created_at <= end_date)

            patients = query.all()

            # Статистика
            total_patients = len(patients)
            new_patients = len(
                [
                    p
                    for p in patients
                    if p.created_at
                    and p.created_at.date()
                    >= (datetime.now().date() - timedelta(days=30))
                ]
            )

            # Группировка по возрасту
            age_groups = {"0-18": 0, "19-35": 0, "36-50": 0, "51-65": 0, "65+": 0}
            gender_stats = {"male": 0, "female": 0, "other": 0}

            for patient in patients:
                # Возрастные группы
                if patient.birth_date:
                    age = (datetime.now().date() - patient.birth_date).days // 365
                    if age <= 18:
                        age_groups["0-18"] += 1
                    elif age <= 35:
                        age_groups["19-35"] += 1
                    elif age <= 50:
                        age_groups["36-50"] += 1
                    elif age <= 65:
                        age_groups["51-65"] += 1
                    else:
                        age_groups["65+"] += 1

                # Пол
                if patient.gender:
                    gender_stats[patient.gender] = (
                        gender_stats.get(patient.gender, 0) + 1
                    )

            report_data = {
                "report_type": "patient_report",
                "generated_at": datetime.now().isoformat(),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
                "summary": {
                    "total_patients": total_patients,
                    "new_patients_last_30_days": new_patients,
                    "age_distribution": age_groups,
                    "gender_distribution": gender_stats,
                },
                "patients": [
                    {
                        "id": p.id,
                        "full_name": p.full_name,
                        "phone": p.phone,
                        "email": p.email,
                        "birth_date": (
                            p.birth_date.isoformat() if p.birth_date else None
                        ),
                        "gender": p.gender,
                        "address": p.address,
                        "created_at": (
                            p.created_at.isoformat() if p.created_at else None
                        ),
                    }
                    for p in patients
                ],
            }

            return self._format_report(report_data, format)

        except Exception as e:
            logger.error(f"Ошибка генерации отчета по пациентам: {e}")
            raise


    def generate_appointments_report(
        self,
        start_date: date = None,
        end_date: date = None,
        doctor_id: int = None,
        department: str = None,
        format: str = "json",
    ) -> dict[str, Any]:
        """Генерирует отчет по записям"""
        try:
            # Объединяем данные из appointments и visits
            appointments_query = self.db.query(Appointment)
            visits_query = self.db.query(Visit)

            # Фильтры по датам
            if start_date:
                appointments_query = appointments_query.filter(
                    Appointment.appointment_date >= start_date
                )
                visits_query = visits_query.filter(Visit.visit_date >= start_date)
            if end_date:
                appointments_query = appointments_query.filter(
                    Appointment.appointment_date <= end_date
                )
                visits_query = visits_query.filter(Visit.visit_date <= end_date)

            # Фильтр по врачу
            if doctor_id:
                appointments_query = appointments_query.filter(
                    Appointment.doctor_id == doctor_id
                )
                visits_query = visits_query.filter(Visit.doctor_id == doctor_id)

            appointments = appointments_query.all()
            visits = visits_query.all()

            # Статистика
            total_appointments = len(appointments) + len(visits)
            completed_appointments = len(
                [a for a in appointments if a.status == "completed"]
            ) + len([v for v in visits if v.status == "completed"])
            cancelled_appointments = len(
                [a for a in appointments if a.status == "cancelled"]
            ) + len([v for v in visits if v.status == "cancelled"])

            # Статистика по врачам
            doctor_stats = {}
            for appointment in appointments:
                if appointment.doctor_id:
                    doctor_stats[appointment.doctor_id] = (
                        doctor_stats.get(appointment.doctor_id, 0) + 1
                    )

            for visit in visits:
                if visit.doctor_id:
                    doctor_stats[visit.doctor_id] = (
                        doctor_stats.get(visit.doctor_id, 0) + 1
                    )

            # Получаем информацию о врачах
            doctor_names = {}
            for doctor_id in doctor_stats.keys():
                doctor = self.db.query(Doctor).filter(Doctor.id == doctor_id).first()
                if doctor and doctor.user:
                    doctor_names[doctor_id] = (
                        doctor.user.full_name or doctor.user.username
                    )
                else:
                    doctor_names[doctor_id] = f"Врач #{doctor_id}"

            # Статистика по дням недели
            weekday_stats = dict.fromkeys(range(7), 0)  # 0 = понедельник
            for appointment in appointments:
                if appointment.appointment_date:
                    weekday_stats[appointment.appointment_date.weekday()] += 1
            for visit in visits:
                if visit.visit_date:
                    weekday_stats[visit.visit_date.weekday()] += 1

            report_data = {
                "report_type": "appointments_report",
                "generated_at": datetime.now().isoformat(),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
                "summary": {
                    "total_appointments": total_appointments,
                    "completed_appointments": completed_appointments,
                    "cancelled_appointments": cancelled_appointments,
                    "completion_rate": (
                        (completed_appointments / total_appointments * 100)
                        if total_appointments > 0
                        else 0
                    ),
                    "doctor_statistics": {
                        doctor_names[doctor_id]: count
                        for doctor_id, count in doctor_stats.items()
                    },
                    "weekday_distribution": {
                        "monday": weekday_stats[0],
                        "tuesday": weekday_stats[1],
                        "wednesday": weekday_stats[2],
                        "thursday": weekday_stats[3],
                        "friday": weekday_stats[4],
                        "saturday": weekday_stats[5],
                        "sunday": weekday_stats[6],
                    },
                },
                "appointments": [],
            }

            # Добавляем данные о записях
            for appointment in appointments:
                patient = (
                    self.db.query(Patient)
                    .filter(Patient.id == appointment.patient_id)
                    .first()
                )
                doctor = (
                    self.db.query(Doctor)
                    .filter(Doctor.id == appointment.doctor_id)
                    .first()
                )

                report_data["appointments"].append(
                    {
                        "id": appointment.id,
                        "type": "appointment",
                        "patient_name": patient.full_name if patient else "Неизвестно",
                        "doctor_name": (
                            doctor.user.full_name
                            if doctor and doctor.user
                            else "Неизвестно"
                        ),
                        "appointment_date": (
                            appointment.appointment_date.isoformat()
                            if appointment.appointment_date
                            else None
                        ),
                        "appointment_time": (
                            appointment.appointment_time.isoformat()
                            if appointment.appointment_time
                            else None
                        ),
                        "status": appointment.status,
                        "notes": appointment.notes,
                        "created_at": (
                            appointment.created_at.isoformat()
                            if appointment.created_at
                            else None
                        ),
                    }
                )

            # Добавляем данные о визитах
            for visit in visits:
                patient = (
                    self.db.query(Patient)
                    .filter(Patient.id == visit.patient_id)
                    .first()
                )
                doctor = (
                    self.db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                )

                # Получаем услуги визита
                visit_services = (
                    self.db.query(VisitService)
                    .filter(VisitService.visit_id == visit.id)
                    .all()
                )
                services_info = []
                for vs in visit_services:
                    service = (
                        self.db.query(Service)
                        .filter(Service.id == vs.service_id)
                        .first()
                    )
                    if service:
                        services_info.append(
                            {
                                "name": service.name,
                                "price": float(vs.price) if vs.price else 0,
                            }
                        )

                report_data["appointments"].append(
                    {
                        "id": visit.id + 20000,  # Offset для различения
                        "type": "visit",
                        "patient_name": patient.full_name if patient else "Неизвестно",
                        "doctor_name": (
                            doctor.user.full_name
                            if doctor and doctor.user
                            else "Неизвестно"
                        ),
                        "appointment_date": (
                            visit.visit_date.isoformat() if visit.visit_date else None
                        ),
                        "appointment_time": (
                            visit.visit_time.isoformat() if visit.visit_time else None
                        ),
                        "status": visit.status,
                        "services": services_info,
                        "total_amount": self._visit_total_amount(visit),
                        "discount_mode": visit.discount_mode,
                        "created_at": (
                            visit.created_at.isoformat() if visit.created_at else None
                        ),
                    }
                )

            return self._format_report(report_data, format)

        except Exception as e:
            logger.error(f"Ошибка генерации отчета по записям: {e}")
            raise


    def generate_financial_report(
        self,
        start_date: date = None,
        end_date: date = None,
        department: str = None,
        format: str = "json",
    ) -> dict[str, Any]:
        """Генерирует финансовый отчет"""
        try:
            # Получаем данные о визитах с оплатами
            query = self.db.query(Visit)

            if start_date:
                query = query.filter(Visit.visit_date >= start_date)
            if end_date:
                query = query.filter(Visit.visit_date <= end_date)

            visits = query.all()

            # Финансовая статистика
            total_revenue = 0
            paid_visits = 0
            unpaid_visits = 0
            discount_amount = 0

            # Статистика по услугам
            service_revenue = {}
            service_counts = {}

            # Статистика по врачам
            doctor_revenue = {}

            # Статистика по способам оплаты
            payment_methods = {"cash": 0, "card": 0, "online": 0, "free": 0}

            for visit in visits:
                visit_amount = self._visit_total_amount(visit)
                total_revenue += visit_amount

                if self._visit_payment_status(visit) == "paid":
                    paid_visits += 1
                else:
                    unpaid_visits += 1

                # Скидки
                if visit.discount_mode in ["repeat", "benefit", "all_free"]:
                    if visit.discount_mode == "all_free":
                        discount_amount += visit_amount
                        payment_methods["free"] += visit_amount
                    else:
                        # Предполагаем скидку 50% для repeat и benefit
                        original_amount = visit_amount * 2
                        discount_amount += original_amount - visit_amount

                # Статистика по врачам
                if visit.doctor_id:
                    doctor_revenue[visit.doctor_id] = (
                        doctor_revenue.get(visit.doctor_id, 0) + visit_amount
                    )

                # Статистика по услугам
                visit_services = (
                    self.db.query(VisitService)
                    .filter(VisitService.visit_id == visit.id)
                    .all()
                )
                for vs in visit_services:
                    service = (
                        self.db.query(Service)
                        .filter(Service.id == vs.service_id)
                        .first()
                    )
                    if service:
                        service_name = service.name
                        service_price = self._as_float(vs.price) * int(vs.qty or 1)

                        service_revenue[service_name] = (
                            service_revenue.get(service_name, 0) + service_price
                        )
                        service_counts[service_name] = (
                            service_counts.get(service_name, 0) + 1
                        )

                # Способы оплаты (упрощенная логика)
                if self._visit_payment_status(visit) == "paid":
                    if visit.discount_mode != "all_free":
                        method = self._visit_payment_method(visit)
                        payment_methods[method] = (
                            payment_methods.get(method, 0) + visit_amount
                        )

            # Получаем информацию о врачах
            doctor_names = {}
            for doctor_id in doctor_revenue.keys():
                doctor = self.db.query(Doctor).filter(Doctor.id == doctor_id).first()
                if doctor and doctor.user:
                    doctor_names[doctor_id] = (
                        doctor.user.full_name or doctor.user.username
                    )
                else:
                    doctor_names[doctor_id] = f"Врач #{doctor_id}"

            report_data = {
                "report_type": "financial_report",
                "generated_at": datetime.now().isoformat(),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
                "summary": {
                    "total_revenue": round(total_revenue, 2),
                    "paid_visits": paid_visits,
                    "unpaid_visits": unpaid_visits,
                    "total_visits": paid_visits + unpaid_visits,
                    "average_visit_cost": (
                        round(total_revenue / (paid_visits + unpaid_visits), 2)
                        if (paid_visits + unpaid_visits) > 0
                        else 0
                    ),
                    "discount_amount": round(discount_amount, 2),
                    "payment_rate": (
                        round(paid_visits / (paid_visits + unpaid_visits) * 100, 2)
                        if (paid_visits + unpaid_visits) > 0
                        else 0
                    ),
                },
                "revenue_by_service": {
                    service: {
                        "revenue": round(revenue, 2),
                        "count": service_counts.get(service, 0),
                        "average_price": round(
                            revenue / service_counts.get(service, 1), 2
                        ),
                    }
                    for service, revenue in service_revenue.items()
                },
                "revenue_by_doctor": {
                    doctor_names[doctor_id]: round(revenue, 2)
                    for doctor_id, revenue in doctor_revenue.items()
                },
                "payment_methods": {
                    method: round(amount, 2)
                    for method, amount in payment_methods.items()
                },
            }

            return self._format_report(report_data, format)

        except Exception as e:
            logger.error(f"Ошибка генерации финансового отчета: {e}")
            raise


