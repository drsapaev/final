"""Reports mixin for ReportingService. Split from reporting_service.py."""
from __future__ import annotations
from app.services.reporting_svc._base import *  # noqa: F401, F403
from app.services.reporting_svc._base import ReportingServiceMixinBase


class ReportsMixin(ReportingServiceMixinBase):
    """Reports methods."""

    def generate_queue_report(
        self,
        start_date: date = None,
        end_date: date = None,
        doctor_id: int = None,
        format: str = "json",
    ) -> dict[str, Any]:
        """Генерирует отчет по очередям"""
        try:
            query = self.db.query(OnlineQueueEntry)

            if start_date:
                query = query.filter(OnlineQueueEntry.created_at >= start_date)
            if end_date:
                query = query.filter(OnlineQueueEntry.created_at <= end_date)
            if doctor_id:
                # Получаем очереди для конкретного врача
                daily_queues = (
                    self.db.query(DailyQueue)
                    .filter(DailyQueue.doctor_id == doctor_id)
                    .all()
                )
                queue_ids = [dq.id for dq in daily_queues]
                if queue_ids:
                    query = query.filter(OnlineQueueEntry.daily_queue_id.in_(queue_ids))
                else:
                    query = query.filter(OnlineQueueEntry.id == -1)  # Пустой результат

            queue_entries = query.all()

            # Статистика
            total_entries = len(queue_entries)
            completed_entries = len(
                [qe for qe in queue_entries if qe.status == "completed"]
            )
            cancelled_entries = len(
                [qe for qe in queue_entries if qe.status == "cancelled"]
            )
            waiting_entries = len(
                [qe for qe in queue_entries if qe.status == "waiting"]
            )

            # Статистика времени ожидания
            wait_times = []
            for entry in queue_entries:
                if entry.called_at and entry.created_at:
                    wait_time = (
                        entry.called_at - entry.created_at
                    ).total_seconds() / 60  # в минутах
                    wait_times.append(wait_time)

            avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0

            # Статистика по часам
            hourly_stats = dict.fromkeys(range(24), 0)
            for entry in queue_entries:
                if entry.created_at:
                    hour = entry.created_at.hour
                    hourly_stats[hour] += 1

            report_data = {
                "report_type": "queue_report",
                "generated_at": datetime.now().isoformat(),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
                "summary": {
                    "total_entries": total_entries,
                    "completed_entries": completed_entries,
                    "cancelled_entries": cancelled_entries,
                    "waiting_entries": waiting_entries,
                    "completion_rate": (
                        round(completed_entries / total_entries * 100, 2)
                        if total_entries > 0
                        else 0
                    ),
                    "average_wait_time_minutes": round(avg_wait_time, 2),
                    "hourly_distribution": hourly_stats,
                },
                "queue_entries": [
                    {
                        "id": qe.id,
                        "queue_number": qe.queue_number,
                        "patient_name": qe.patient_name,
                        "patient_phone": qe.patient_phone,
                        "status": qe.status,
                        "created_at": (
                            qe.created_at.isoformat() if qe.created_at else None
                        ),
                        "called_at": qe.called_at.isoformat() if qe.called_at else None,
                        "completed_at": (
                            qe.completed_at.isoformat() if qe.completed_at else None
                        ),
                        "wait_time_minutes": (
                            round(
                                (qe.called_at - qe.created_at).total_seconds() / 60, 2
                            )
                            if qe.called_at and qe.created_at
                            else None
                        ),
                    }
                    for qe in queue_entries
                ],
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
        format: str = "json",
    ) -> dict[str, Any]:
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
                appointments_query = self.db.query(Appointment).filter(
                    Appointment.doctor_id == doctor.id
                )
                visits_query = self.db.query(Visit).filter(Visit.doctor_id == doctor.id)

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

                appointments = appointments_query.all()
                visits = visits_query.all()

                total_appointments = len(appointments) + len(visits)
                completed_appointments = len(
                    [a for a in appointments if a.status == "completed"]
                ) + len([v for v in visits if v.status == "completed"])

                # Доходы
                total_revenue = sum(self._visit_total_amount(v) for v in visits)

                # Средняя продолжительность приема (упрощенная логика)
                avg_duration = 30  # По умолчанию 30 минут

                doctor_name = (
                    doctor.user.full_name if doctor.user else f"Врач #{doctor.id}"
                )

                doctor_stats[doctor_name] = {
                    "doctor_id": doctor.id,
                    "total_appointments": total_appointments,
                    "completed_appointments": completed_appointments,
                    "completion_rate": (
                        round(completed_appointments / total_appointments * 100, 2)
                        if total_appointments > 0
                        else 0
                    ),
                    "total_revenue": round(total_revenue, 2),
                    "average_revenue_per_appointment": (
                        round(total_revenue / total_appointments, 2)
                        if total_appointments > 0
                        else 0
                    ),
                    "average_duration_minutes": avg_duration,
                    "specialization": doctor.specialty or "Не указано",
                }

            report_data = {
                "report_type": "doctor_performance_report",
                "generated_at": datetime.now().isoformat(),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
                "summary": {
                    "total_doctors": len(doctors),
                    "total_appointments": sum(
                        [stats["total_appointments"] for stats in doctor_stats.values()]
                    ),
                    "total_revenue": sum(
                        [stats["total_revenue"] for stats in doctor_stats.values()]
                    ),
                    "average_completion_rate": (
                        round(
                            sum(
                                [
                                    stats["completion_rate"]
                                    for stats in doctor_stats.values()
                                ]
                            )
                            / len(doctor_stats),
                            2,
                        )
                        if doctor_stats
                        else 0
                    ),
                },
                "doctor_performance": doctor_stats,
            }

            return self._format_report(report_data, format)

        except Exception as e:
            logger.error(f"Ошибка генерации отчета по производительности врачей: {e}")
            raise


    def generate_daily_summary(self, target_date: date = None) -> dict[str, Any]:
        """Генерирует ежедневную сводку"""
        try:
            if not target_date:
                target_date = datetime.now().date()

            # Получаем визиты за день
            visits = (
                self.db.query(Visit)
                .filter(Visit.visit_date == target_date)
                .all()
            )

            # Получаем записи очереди за день
            queue_entries = (
                self.db.query(OnlineQueueEntry)
                .filter(func.date(OnlineQueueEntry.created_at) == target_date)
                .all()
            )

            # Получаем записи на прием за день
            appointments = (
                self.db.query(Appointment)
                .filter(Appointment.appointment_date == target_date)
                .all()
            )

            # Рассчитываем статистику
            total_patients_served = len(visits)
            total_revenue = sum(self._visit_total_amount(v) for v in visits)

            # Новые пациенты за сегодня
            new_patients = (
                self.db.query(Patient)
                .filter(func.date(Patient.created_at) == target_date)
                .count()
            )

            # Завершенные визиты
            completed_visits = len([v for v in visits if v.status == "completed"])

            # Статистика очереди
            queue_completed = len([qe for qe in queue_entries if qe.status == "completed"])
            queue_waiting = len([qe for qe in queue_entries if qe.status == "waiting"])

            return {
                "success": True,
                "date": target_date.isoformat(),
                "summary": {
                    "total_patients_served": total_patients_served,
                    "total_revenue": round(total_revenue, 2),
                    "new_patients": new_patients,
                    "completed_visits": completed_visits,
                    "total_appointments": len(appointments),
                    "queue_entries": len(queue_entries),
                    "queue_completed": queue_completed,
                    "queue_waiting": queue_waiting,
                },
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Ошибка генерации ежедневной сводки: {e}")
            return {"error": str(e)}

    # ===================== ФОРМАТИРОВАНИЕ ОТЧЕТОВ =====================


    def _format_report(self, data: dict[str, Any], format: str) -> dict[str, Any]:
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


    def _convert_to_csv(self, data: dict[str, Any]) -> dict[str, Any]:
        """Конвертирует данные в CSV"""
        try:
            csv_content = StringIO()

            # Определяем тип отчета и создаем соответствующий CSV
            report_type = data.get("report_type", "unknown")

            if report_type == "patient_report" and "patients" in data:
                writer = csv.DictWriter(
                    csv_content,
                    fieldnames=[
                        "id",
                        "full_name",
                        "phone",
                        "email",
                        "birth_date",
                        "gender",
                        "address",
                        "created_at",
                    ],
                )
                writer.writeheader()
                writer.writerows(data["patients"])

            elif report_type == "appointments_report" and "appointments" in data:
                writer = csv.DictWriter(
                    csv_content,
                    fieldnames=[
                        "id",
                        "type",
                        "patient_name",
                        "doctor_name",
                        "appointment_date",
                        "appointment_time",
                        "status",
                        "total_amount",
                        "created_at",
                    ],
                )
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
                        "created_at": appointment["created_at"],
                    }
                    writer.writerow(csv_row)

            elif report_type == "queue_report" and "queue_entries" in data:
                writer = csv.DictWriter(
                    csv_content,
                    fieldnames=[
                        "id",
                        "queue_number",
                        "patient_name",
                        "patient_phone",
                        "status",
                        "created_at",
                        "called_at",
                        "completed_at",
                        "wait_time_minutes",
                    ],
                )
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
                "data": data,  # Оригинальные данные
            }

        except Exception as e:
            logger.error(f"Ошибка конвертации в CSV: {e}")
            return {"error": str(e), "data": data}


    def _convert_to_excel(self, data: dict[str, Any]) -> dict[str, Any]:
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
                            services_data.append(
                                {
                                    "service": service,
                                    "revenue": info["revenue"],
                                    "count": info["count"],
                                    "average_price": info["average_price"],
                                }
                            )
                        services_df = pd.DataFrame(services_data)
                        services_df.to_excel(
                            writer, sheet_name='Доходы по услугам', index=False
                        )

                    if "revenue_by_doctor" in data:
                        doctors_data = [
                            {"doctor": doctor, "revenue": revenue}
                            for doctor, revenue in data["revenue_by_doctor"].items()
                        ]
                        doctors_df = pd.DataFrame(doctors_data)
                        doctors_df.to_excel(
                            writer, sheet_name='Доходы по врачам', index=False
                        )

                elif report_type == "queue_report" and "queue_entries" in data:
                    queue_df = pd.DataFrame(data["queue_entries"])
                    queue_df.to_excel(writer, sheet_name='Очередь', index=False)

                elif (
                    report_type == "doctor_performance_report"
                    and "doctor_performance" in data
                ):
                    performance_data = []
                    for doctor, stats in data["doctor_performance"].items():
                        stats_copy = stats.copy()
                        stats_copy["doctor_name"] = doctor
                        performance_data.append(stats_copy)
                    performance_df = pd.DataFrame(performance_data)
                    performance_df.to_excel(
                        writer, sheet_name='Производительность', index=False
                    )

            # Получаем размер файла
            file_size = os.path.getsize(filepath)

            return {
                "format": "excel",
                "filename": filename,
                "filepath": filepath,
                "size": file_size,
                "data": data,
            }

        except Exception as e:
            logger.error(f"Ошибка конвертации в Excel: {e}")
            # Fallback to CSV if Excel fails
            return self._convert_to_csv(data)


    def _convert_to_pdf(self, data: dict[str, Any]) -> dict[str, Any]:
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
                "report_title": data.get("report_type", "Отчет")
                .replace("_", " ")
                .title(),
                "generated_at": data.get("generated_at", ""),
                "period": data.get("period", {}),
                "summary": data.get("summary", {}),
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
                "note": "PDF генерация требует дополнительных библиотек. Создан HTML файл.",
            }

        except Exception as e:
            logger.error(f"Ошибка конвертации в PDF: {e}")
            return {"error": str(e), "data": data}

    # ===================== АВТОМАТИЧЕСКИЕ ОТЧЕТЫ =====================


    def schedule_automatic_report(
        self,
        report_type: str,
        schedule: str,  # "daily", "weekly", "monthly"
        recipients: list[str],
        format: str = "excel",
        filters: dict[str, Any] = None,
    ) -> dict[str, Any]:
        """Планирует автоматический отчет"""
        try:
            # В реальной системе здесь была бы интеграция с arq или другим планировщиком
            scheduled_report = {
                "id": f"auto_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "report_type": report_type,
                "schedule": schedule,
                "recipients": recipients,
                "format": format,
                "filters": filters or {},
                "created_at": datetime.now().isoformat(),
                "next_run": self._calculate_next_run(schedule),
                "status": "scheduled",
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
            next_run = now.replace(
                hour=9, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
        elif schedule == "weekly":
            days_ahead = 0 - now.weekday()  # Понедельник
            if days_ahead <= 0:
                days_ahead += 7
            next_run = now.replace(
                hour=9, minute=0, second=0, microsecond=0
            ) + timedelta(days=days_ahead)
        elif schedule == "monthly":
            if now.month == 12:
                next_run = now.replace(
                    year=now.year + 1,
                    month=1,
                    day=1,
                    hour=9,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            else:
                next_run = now.replace(
                    month=now.month + 1,
                    day=1,
                    hour=9,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
        else:
            next_run = now + timedelta(days=1)

        return next_run.isoformat()

    # ===================== УТИЛИТЫ =====================


    def get_available_reports(self) -> list[dict[str, Any]]:
        """Возвращает список доступных типов отчетов"""
        return [
            {
                "type": "patient_report",
                "name": "Отчет по пациентам",
                "description": "Статистика и список пациентов",
                "parameters": ["start_date", "end_date", "department"],
            },
            {
                "type": "appointments_report",
                "name": "Отчет по записям",
                "description": "Статистика записей и визитов",
                "parameters": ["start_date", "end_date", "doctor_id", "department"],
            },
            {
                "type": "financial_report",
                "name": "Финансовый отчет",
                "description": "Доходы, расходы, статистика платежей",
                "parameters": ["start_date", "end_date", "department"],
            },
            {
                "type": "queue_report",
                "name": "Отчет по очередям",
                "description": "Статистика очередей и времени ожидания",
                "parameters": ["start_date", "end_date", "doctor_id"],
            },
            {
                "type": "doctor_performance_report",
                "name": "Отчет по производительности врачей",
                "description": "Статистика работы врачей",
                "parameters": ["start_date", "end_date", "doctor_id"],
            },
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


