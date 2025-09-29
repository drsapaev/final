"""
Сервис для генерации расширенных отчетов
"""
import logging
import os
import json
import csv
from io import BytesIO, StringIO
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, text
import pandas as pd
from jinja2 import Template

from app.models.patient import Patient
from app.models.clinic import Doctor
from app.models.service import Service
from app.models.appointment import Appointment
from app.models.visit import Visit, VisitService
from app.models.online_queue import OnlineQueueEntry, DailyQueue
from app.models.user import User
from app.core.config import settings

logger = logging.getLogger(__name__)


class ReportingService:
    """Сервис для генерации отчетов"""
    
    def __init__(self, db: Session):
        self.db = db
        self.reports_dir = "reports"
        os.makedirs(self.reports_dir, exist_ok=True)
    
    # ===================== ОСНОВНЫЕ ОТЧЕТЫ =====================
    
    def generate_patient_report(
        self, 
        start_date: date = None,
        end_date: date = None,
        department: str = None,
        format: str = "json"
    ) -> Dict[str, Any]:
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
            new_patients = len([p for p in patients if p.created_at and p.created_at.date() >= (datetime.now().date() - timedelta(days=30))])
            
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
                    gender_stats[patient.gender] = gender_stats.get(patient.gender, 0) + 1
            
            report_data = {
                "report_type": "patient_report",
                "generated_at": datetime.now().isoformat(),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                },
                "summary": {
                    "total_patients": total_patients,
                    "new_patients_last_30_days": new_patients,
                    "age_distribution": age_groups,
                    "gender_distribution": gender_stats
                },
                "patients": [
                    {
                        "id": p.id,
                        "full_name": p.full_name,
                        "phone": p.phone,
                        "email": p.email,
                        "birth_date": p.birth_date.isoformat() if p.birth_date else None,
                        "gender": p.gender,
                        "address": p.address,
                        "created_at": p.created_at.isoformat() if p.created_at else None
                    }
                    for p in patients
                ]
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
        format: str = "json"
    ) -> Dict[str, Any]:
        """Генерирует отчет по записям"""
        try:
            # Объединяем данные из appointments и visits
            appointments_query = self.db.query(Appointment)
            visits_query = self.db.query(Visit)
            
            # Фильтры по датам
            if start_date:
                appointments_query = appointments_query.filter(Appointment.appointment_date >= start_date)
                visits_query = visits_query.filter(Visit.visit_date >= start_date)
            if end_date:
                appointments_query = appointments_query.filter(Appointment.appointment_date <= end_date)
                visits_query = visits_query.filter(Visit.visit_date <= end_date)
            
            # Фильтр по врачу
            if doctor_id:
                appointments_query = appointments_query.filter(Appointment.doctor_id == doctor_id)
                visits_query = visits_query.filter(Visit.doctor_id == doctor_id)
            
            appointments = appointments_query.all()
            visits = visits_query.all()
            
            # Статистика
            total_appointments = len(appointments) + len(visits)
            completed_appointments = len([a for a in appointments if a.status == "completed"]) + len([v for v in visits if v.status == "completed"])
            cancelled_appointments = len([a for a in appointments if a.status == "cancelled"]) + len([v for v in visits if v.status == "cancelled"])
            
            # Статистика по врачам
            doctor_stats = {}
            for appointment in appointments:
                if appointment.doctor_id:
                    doctor_stats[appointment.doctor_id] = doctor_stats.get(appointment.doctor_id, 0) + 1
            
            for visit in visits:
                if visit.doctor_id:
                    doctor_stats[visit.doctor_id] = doctor_stats.get(visit.doctor_id, 0) + 1
            
            # Получаем информацию о врачах
            doctor_names = {}
            for doctor_id in doctor_stats.keys():
                doctor = self.db.query(Doctor).filter(Doctor.id == doctor_id).first()
                if doctor and doctor.user:
                    doctor_names[doctor_id] = doctor.user.full_name or doctor.user.username
                else:
                    doctor_names[doctor_id] = f"Врач #{doctor_id}"
            
            # Статистика по дням недели
            weekday_stats = {i: 0 for i in range(7)}  # 0 = понедельник
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
                    "end_date": end_date.isoformat() if end_date else None
                },
                "summary": {
                    "total_appointments": total_appointments,
                    "completed_appointments": completed_appointments,
                    "cancelled_appointments": cancelled_appointments,
                    "completion_rate": (completed_appointments / total_appointments * 100) if total_appointments > 0 else 0,
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
                        "sunday": weekday_stats[6]
                    }
                },
                "appointments": []
            }
            
            # Добавляем данные о записях
            for appointment in appointments:
                patient = self.db.query(Patient).filter(Patient.id == appointment.patient_id).first()
                doctor = self.db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
                
                report_data["appointments"].append({
                    "id": appointment.id,
                    "type": "appointment",
                    "patient_name": patient.full_name if patient else "Неизвестно",
                    "doctor_name": doctor.user.full_name if doctor and doctor.user else "Неизвестно",
                    "appointment_date": appointment.appointment_date.isoformat() if appointment.appointment_date else None,
                    "appointment_time": appointment.appointment_time.isoformat() if appointment.appointment_time else None,
                    "status": appointment.status,
                    "notes": appointment.notes,
                    "created_at": appointment.created_at.isoformat() if appointment.created_at else None
                })
            
            # Добавляем данные о визитах
            for visit in visits:
                patient = self.db.query(Patient).filter(Patient.id == visit.patient_id).first()
                doctor = self.db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                
                # Получаем услуги визита
                visit_services = self.db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
                services_info = []
                for vs in visit_services:
                    service = self.db.query(Service).filter(Service.id == vs.service_id).first()
                    if service:
                        services_info.append({
                            "name": service.name,
                            "price": float(vs.price) if vs.price else 0
                        })
                
                report_data["appointments"].append({
                    "id": visit.id + 20000,  # Offset для различения
                    "type": "visit",
                    "patient_name": patient.full_name if patient else "Неизвестно",
                    "doctor_name": doctor.user.full_name if doctor and doctor.user else "Неизвестно",
                    "appointment_date": visit.visit_date.isoformat() if visit.visit_date else None,
                    "appointment_time": visit.visit_time.isoformat() if visit.visit_time else None,
                    "status": visit.status,
                    "services": services_info,
                    "total_amount": float(visit.total_amount) if visit.total_amount else 0,
                    "discount_mode": visit.discount_mode,
                    "created_at": visit.created_at.isoformat() if visit.created_at else None
                })
            
            return self._format_report(report_data, format)
            
        except Exception as e:
            logger.error(f"Ошибка генерации отчета по записям: {e}")
            raise
    
    def generate_financial_report(
        self,
        start_date: date = None,
        end_date: date = None,
        department: str = None,
        format: str = "json"
    ) -> Dict[str, Any]:
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
                visit_amount = float(visit.total_amount) if visit.total_amount else 0
                total_revenue += visit_amount
                
                if visit.payment_status == "paid":
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
                    doctor_revenue[visit.doctor_id] = doctor_revenue.get(visit.doctor_id, 0) + visit_amount
                
                # Статистика по услугам
                visit_services = self.db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
                for vs in visit_services:
                    service = self.db.query(Service).filter(Service.id == vs.service_id).first()
                    if service:
                        service_name = service.name
                        service_price = float(vs.price) if vs.price else 0
                        
                        service_revenue[service_name] = service_revenue.get(service_name, 0) + service_price
                        service_counts[service_name] = service_counts.get(service_name, 0) + 1
                
                # Способы оплаты (упрощенная логика)
                if visit.payment_status == "paid":
                    if visit.discount_mode != "all_free":
                        payment_methods["card"] += visit_amount  # По умолчанию считаем картой
            
            # Получаем информацию о врачах
            doctor_names = {}
            for doctor_id in doctor_revenue.keys():
                doctor = self.db.query(Doctor).filter(Doctor.id == doctor_id).first()
                if doctor and doctor.user:
                    doctor_names[doctor_id] = doctor.user.full_name or doctor.user.username
                else:
                    doctor_names[doctor_id] = f"Врач #{doctor_id}"
            
            report_data = {
                "report_type": "financial_report",
                "generated_at": datetime.now().isoformat(),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                },
                "summary": {
                    "total_revenue": round(total_revenue, 2),
                    "paid_visits": paid_visits,
                    "unpaid_visits": unpaid_visits,
                    "total_visits": paid_visits + unpaid_visits,
                    "average_visit_cost": round(total_revenue / (paid_visits + unpaid_visits), 2) if (paid_visits + unpaid_visits) > 0 else 0,
                    "discount_amount": round(discount_amount, 2),
                    "payment_rate": round(paid_visits / (paid_visits + unpaid_visits) * 100, 2) if (paid_visits + unpaid_visits) > 0 else 0
                },
                "revenue_by_service": {
                    service: {
                        "revenue": round(revenue, 2),
                        "count": service_counts.get(service, 0),
                        "average_price": round(revenue / service_counts.get(service, 1), 2)
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
                }
            }
            
            return self._format_report(report_data, format)
            
        except Exception as e:
            logger.error(f"Ошибка генерации финансового отчета: {e}")
            raise
    
    def generate_queue_report(
        self,
        start_date: date = None,
        end_date: date = None,
        doctor_id: int = None,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Генерирует отчет по очередям"""
        try:
            query = self.db.query(OnlineQueueEntry)
            
            if start_date:
                query = query.filter(OnlineQueueEntry.created_at >= start_date)
            if end_date:
                query = query.filter(OnlineQueueEntry.created_at <= end_date)
            if doctor_id:
                # Получаем очереди для конкретного врача
                daily_queues = self.db.query(DailyQueue).filter(DailyQueue.doctor_id == doctor_id).all()
                queue_ids = [dq.id for dq in daily_queues]
                if queue_ids:
                    query = query.filter(OnlineQueueEntry.daily_queue_id.in_(queue_ids))
                else:
                    query = query.filter(OnlineQueueEntry.id == -1)  # Пустой результат
            
            queue_entries = query.all()
            
            # Статистика
            total_entries = len(queue_entries)
            completed_entries = len([qe for qe in queue_entries if qe.status == "completed"])
            cancelled_entries = len([qe for qe in queue_entries if qe.status == "cancelled"])
            waiting_entries = len([qe for qe in queue_entries if qe.status == "waiting"])
            
            # Статистика времени ожидания
            wait_times = []
            for entry in queue_entries:
                if entry.called_at and entry.created_at:
                    wait_time = (entry.called_at - entry.created_at).total_seconds() / 60  # в минутах
                    wait_times.append(wait_time)
            
            avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0
            
            # Статистика по часам
            hourly_stats = {i: 0 for i in range(24)}
            for entry in queue_entries:
                if entry.created_at:
                    hour = entry.created_at.hour
                    hourly_stats[hour] += 1
            
            report_data = {
                "report_type": "queue_report",
                "generated_at": datetime.now().isoformat(),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                },
                "summary": {
                    "total_entries": total_entries,
                    "completed_entries": completed_entries,
                    "cancelled_entries": cancelled_entries,
                    "waiting_entries": waiting_entries,
                    "completion_rate": round(completed_entries / total_entries * 100, 2) if total_entries > 0 else 0,
                    "average_wait_time_minutes": round(avg_wait_time, 2),
                    "hourly_distribution": hourly_stats
                },
                "queue_entries": [
                    {
                        "id": qe.id,
                        "queue_number": qe.queue_number,
                        "patient_name": qe.patient_name,
                        "patient_phone": qe.patient_phone,
                        "status": qe.status,
                        "created_at": qe.created_at.isoformat() if qe.created_at else None,
                        "called_at": qe.called_at.isoformat() if qe.called_at else None,
                        "completed_at": qe.completed_at.isoformat() if qe.completed_at else None,
                        "wait_time_minutes": round((qe.called_at - qe.created_at).total_seconds() / 60, 2) if qe.called_at and qe.created_at else None
                    }
                    for qe in queue_entries
                ]
            }
            
            return self._format_report(report_data, format)
            
        except Exception as e:
            logger.error(f"Ошибка генерации отчета по очередям: {e}")
            raise
    
    def generate_doctor_performance_report(
        self,
        start_date: date = None,
        end_date: date = None,
        doctor_id: int = None,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Генерирует отчет по производительности врачей"""
        try:
            # Получаем всех врачей или конкретного врача
            doctors_query = self.db.query(Doctor)
            if doctor_id:
                doctors_query = doctors_query.filter(Doctor.id == doctor_id)
            
            doctors = doctors_query.all()
            doctor_stats = {}
            
            for doctor in doctors:
                # Статистика по записям
                appointments_query = self.db.query(Appointment).filter(Appointment.doctor_id == doctor.id)
                visits_query = self.db.query(Visit).filter(Visit.doctor_id == doctor.id)
                
                if start_date:
                    appointments_query = appointments_query.filter(Appointment.appointment_date >= start_date)
                    visits_query = visits_query.filter(Visit.visit_date >= start_date)
                if end_date:
                    appointments_query = appointments_query.filter(Appointment.appointment_date <= end_date)
                    visits_query = visits_query.filter(Visit.visit_date <= end_date)
                
                appointments = appointments_query.all()
                visits = visits_query.all()
                
                total_appointments = len(appointments) + len(visits)
                completed_appointments = len([a for a in appointments if a.status == "completed"]) + len([v for v in visits if v.status == "completed"])
                
                # Доходы
                total_revenue = sum([float(v.total_amount) for v in visits if v.total_amount])
                
                # Средняя продолжительность приема (упрощенная логика)
                avg_duration = 30  # По умолчанию 30 минут
                
                doctor_name = doctor.user.full_name if doctor.user else f"Врач #{doctor.id}"
                
                doctor_stats[doctor_name] = {
                    "doctor_id": doctor.id,
                    "total_appointments": total_appointments,
                    "completed_appointments": completed_appointments,
                    "completion_rate": round(completed_appointments / total_appointments * 100, 2) if total_appointments > 0 else 0,
                    "total_revenue": round(total_revenue, 2),
                    "average_revenue_per_appointment": round(total_revenue / total_appointments, 2) if total_appointments > 0 else 0,
                    "average_duration_minutes": avg_duration,
                    "specialization": doctor.specialty or "Не указано"
                }
            
            report_data = {
                "report_type": "doctor_performance_report",
                "generated_at": datetime.now().isoformat(),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                },
                "summary": {
                    "total_doctors": len(doctors),
                    "total_appointments": sum([stats["total_appointments"] for stats in doctor_stats.values()]),
                    "total_revenue": sum([stats["total_revenue"] for stats in doctor_stats.values()]),
                    "average_completion_rate": round(sum([stats["completion_rate"] for stats in doctor_stats.values()]) / len(doctor_stats), 2) if doctor_stats else 0
                },
                "doctor_performance": doctor_stats
            }
            
            return self._format_report(report_data, format)
            
        except Exception as e:
            logger.error(f"Ошибка генерации отчета по производительности врачей: {e}")
            raise
    
    # ===================== ФОРМАТИРОВАНИЕ ОТЧЕТОВ =====================
    
    def _format_report(self, data: Dict[str, Any], format: str) -> Dict[str, Any]:
        """Форматирует отчет в указанный формат"""
        if format.lower() == "json":
            return data
        elif format.lower() == "csv":
            return self._convert_to_csv(data)
        elif format.lower() == "excel":
            return self._convert_to_excel(data)
        elif format.lower() == "pdf":
            return self._convert_to_pdf(data)
        else:
            return data
    
    def _convert_to_csv(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Конвертирует данные в CSV"""
        try:
            csv_content = StringIO()
            
            # Определяем тип отчета и создаем соответствующий CSV
            report_type = data.get("report_type", "unknown")
            
            if report_type == "patient_report" and "patients" in data:
                writer = csv.DictWriter(csv_content, fieldnames=[
                    "id", "full_name", "phone", "email", "birth_date", "gender", "address", "created_at"
                ])
                writer.writeheader()
                writer.writerows(data["patients"])
            
            elif report_type == "appointments_report" and "appointments" in data:
                writer = csv.DictWriter(csv_content, fieldnames=[
                    "id", "type", "patient_name", "doctor_name", "appointment_date", 
                    "appointment_time", "status", "total_amount", "created_at"
                ])
                writer.writeheader()
                for appointment in data["appointments"]:
                    # Упрощаем данные для CSV
                    csv_row = {
                        "id": appointment["id"],
                        "type": appointment["type"],
                        "patient_name": appointment["patient_name"],
                        "doctor_name": appointment["doctor_name"],
                        "appointment_date": appointment["appointment_date"],
                        "appointment_time": appointment["appointment_time"],
                        "status": appointment["status"],
                        "total_amount": appointment.get("total_amount", ""),
                        "created_at": appointment["created_at"]
                    }
                    writer.writerow(csv_row)
            
            elif report_type == "queue_report" and "queue_entries" in data:
                writer = csv.DictWriter(csv_content, fieldnames=[
                    "id", "queue_number", "patient_name", "patient_phone", "status",
                    "created_at", "called_at", "completed_at", "wait_time_minutes"
                ])
                writer.writeheader()
                writer.writerows(data["queue_entries"])
            
            csv_string = csv_content.getvalue()
            csv_content.close()
            
            # Сохраняем файл
            filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(self.reports_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                f.write(csv_string)
            
            return {
                "format": "csv",
                "filename": filename,
                "filepath": filepath,
                "size": len(csv_string.encode('utf-8')),
                "data": data  # Оригинальные данные
            }
            
        except Exception as e:
            logger.error(f"Ошибка конвертации в CSV: {e}")
            return {"error": str(e), "data": data}
    
    def _convert_to_excel(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Конвертирует данные в Excel"""
        try:
            # Создаем Excel файл
            filename = f"{data.get('report_type', 'report')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = os.path.join(self.reports_dir, filename)
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Сводка
                if "summary" in data:
                    summary_df = pd.DataFrame([data["summary"]])
                    summary_df.to_excel(writer, sheet_name='Сводка', index=False)
                
                # Основные данные
                report_type = data.get("report_type", "unknown")
                
                if report_type == "patient_report" and "patients" in data:
                    patients_df = pd.DataFrame(data["patients"])
                    patients_df.to_excel(writer, sheet_name='Пациенты', index=False)
                
                elif report_type == "appointments_report" and "appointments" in data:
                    appointments_df = pd.DataFrame(data["appointments"])
                    appointments_df.to_excel(writer, sheet_name='Записи', index=False)
                
                elif report_type == "financial_report":
                    if "revenue_by_service" in data:
                        services_data = []
                        for service, info in data["revenue_by_service"].items():
                            services_data.append({
                                "service": service,
                                "revenue": info["revenue"],
                                "count": info["count"],
                                "average_price": info["average_price"]
                            })
                        services_df = pd.DataFrame(services_data)
                        services_df.to_excel(writer, sheet_name='Доходы по услугам', index=False)
                    
                    if "revenue_by_doctor" in data:
                        doctors_data = [
                            {"doctor": doctor, "revenue": revenue}
                            for doctor, revenue in data["revenue_by_doctor"].items()
                        ]
                        doctors_df = pd.DataFrame(doctors_data)
                        doctors_df.to_excel(writer, sheet_name='Доходы по врачам', index=False)
                
                elif report_type == "queue_report" and "queue_entries" in data:
                    queue_df = pd.DataFrame(data["queue_entries"])
                    queue_df.to_excel(writer, sheet_name='Очередь', index=False)
                
                elif report_type == "doctor_performance_report" and "doctor_performance" in data:
                    performance_data = []
                    for doctor, stats in data["doctor_performance"].items():
                        stats_copy = stats.copy()
                        stats_copy["doctor_name"] = doctor
                        performance_data.append(stats_copy)
                    performance_df = pd.DataFrame(performance_data)
                    performance_df.to_excel(writer, sheet_name='Производительность', index=False)
            
            # Получаем размер файла
            file_size = os.path.getsize(filepath)
            
            return {
                "format": "excel",
                "filename": filename,
                "filepath": filepath,
                "size": file_size,
                "data": data
            }
            
        except Exception as e:
            logger.error(f"Ошибка конвертации в Excel: {e}")
            # Fallback to CSV if Excel fails
            return self._convert_to_csv(data)
    
    def _convert_to_pdf(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Конвертирует данные в PDF"""
        try:
            # Простой HTML шаблон для PDF
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>{{ report_title }}</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    .header { text-align: center; margin-bottom: 30px; }
                    .summary { background-color: #f5f5f5; padding: 15px; margin-bottom: 20px; }
                    .summary h3 { margin-top: 0; }
                    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
                    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                    th { background-color: #f2f2f2; }
                    .number { text-align: right; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>{{ report_title }}</h1>
                    <p>Сгенерирован: {{ generated_at }}</p>
                    {% if period.start_date %}
                    <p>Период: {{ period.start_date }} - {{ period.end_date }}</p>
                    {% endif %}
                </div>
                
                {% if summary %}
                <div class="summary">
                    <h3>Сводка</h3>
                    {% for key, value in summary.items() %}
                    <p><strong>{{ key }}:</strong> {{ value }}</p>
                    {% endfor %}
                </div>
                {% endif %}
                
                <!-- Здесь можно добавить таблицы с данными -->
                <p>Подробные данные доступны в JSON формате.</p>
            </body>
            </html>
            """
            
            # Подготавливаем данные для шаблона
            template_data = {
                "report_title": data.get("report_type", "Отчет").replace("_", " ").title(),
                "generated_at": data.get("generated_at", ""),
                "period": data.get("period", {}),
                "summary": data.get("summary", {})
            }
            
            # Рендерим HTML
            template = Template(html_template)
            html_content = template.render(**template_data)
            
            # Сохраняем HTML файл (в реальной системе здесь был бы PDF)
            filename = f"{data.get('report_type', 'report')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            filepath = os.path.join(self.reports_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            file_size = len(html_content.encode('utf-8'))
            
            return {
                "format": "pdf",  # На самом деле HTML, но для демонстрации
                "filename": filename,
                "filepath": filepath,
                "size": file_size,
                "data": data,
                "note": "PDF генерация требует дополнительных библиотек. Создан HTML файл."
            }
            
        except Exception as e:
            logger.error(f"Ошибка конвертации в PDF: {e}")
            return {"error": str(e), "data": data}
    
    # ===================== АВТОМАТИЧЕСКИЕ ОТЧЕТЫ =====================
    
    def schedule_automatic_report(
        self,
        report_type: str,
        schedule: str,  # "daily", "weekly", "monthly"
        recipients: List[str],
        format: str = "excel",
        filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Планирует автоматический отчет"""
        try:
            # В реальной системе здесь была бы интеграция с Celery или другим планировщиком
            scheduled_report = {
                "id": f"auto_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "report_type": report_type,
                "schedule": schedule,
                "recipients": recipients,
                "format": format,
                "filters": filters or {},
                "created_at": datetime.now().isoformat(),
                "next_run": self._calculate_next_run(schedule),
                "status": "scheduled"
            }
            
            # Сохраняем конфигурацию (в реальной системе - в БД)
            config_filename = f"scheduled_report_{scheduled_report['id']}.json"
            config_filepath = os.path.join(self.reports_dir, config_filename)
            
            with open(config_filepath, 'w', encoding='utf-8') as f:
                json.dump(scheduled_report, f, ensure_ascii=False, indent=2)
            
            return scheduled_report
            
        except Exception as e:
            logger.error(f"Ошибка планирования автоматического отчета: {e}")
            raise
    
    def _calculate_next_run(self, schedule: str) -> str:
        """Вычисляет время следующего запуска"""
        now = datetime.now()
        
        if schedule == "daily":
            next_run = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        elif schedule == "weekly":
            days_ahead = 0 - now.weekday()  # Понедельник
            if days_ahead <= 0:
                days_ahead += 7
            next_run = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
        elif schedule == "monthly":
            if now.month == 12:
                next_run = now.replace(year=now.year + 1, month=1, day=1, hour=9, minute=0, second=0, microsecond=0)
            else:
                next_run = now.replace(month=now.month + 1, day=1, hour=9, minute=0, second=0, microsecond=0)
        else:
            next_run = now + timedelta(days=1)
        
        return next_run.isoformat()
    
    # ===================== УТИЛИТЫ =====================
    
    def get_available_reports(self) -> List[Dict[str, Any]]:
        """Возвращает список доступных типов отчетов"""
        return [
            {
                "type": "patient_report",
                "name": "Отчет по пациентам",
                "description": "Статистика и список пациентов",
                "parameters": ["start_date", "end_date", "department"]
            },
            {
                "type": "appointments_report",
                "name": "Отчет по записям",
                "description": "Статистика записей и визитов",
                "parameters": ["start_date", "end_date", "doctor_id", "department"]
            },
            {
                "type": "financial_report",
                "name": "Финансовый отчет",
                "description": "Доходы, расходы, статистика платежей",
                "parameters": ["start_date", "end_date", "department"]
            },
            {
                "type": "queue_report",
                "name": "Отчет по очередям",
                "description": "Статистика очередей и времени ожидания",
                "parameters": ["start_date", "end_date", "doctor_id"]
            },
            {
                "type": "doctor_performance_report",
                "name": "Отчет по производительности врачей",
                "description": "Статистика работы врачей",
                "parameters": ["start_date", "end_date", "doctor_id"]
            }
        ]
    
    def cleanup_old_reports(self, days: int = 30) -> int:
        """Очищает старые файлы отчетов"""
        try:
            deleted_count = 0
            cutoff_time = datetime.now() - timedelta(days=days)
            
            for filename in os.listdir(self.reports_dir):
                filepath = os.path.join(self.reports_dir, filename)
                if os.path.isfile(filepath):
                    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if file_time < cutoff_time:
                        os.remove(filepath)
                        deleted_count += 1
            
            logger.info(f"Удалено {deleted_count} старых файлов отчетов")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых отчетов: {e}")
            return 0


def get_reporting_service(db: Session) -> ReportingService:
    """Получить экземпляр сервиса отчетов"""
    return ReportingService(db)

