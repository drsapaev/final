import calendar
import statistics
from bisect import bisect_right
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Row, and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.specialties import specialty_variants
from app.models.appointment import Appointment
from app.models.department import Department
from app.models.patient import Patient
from app.models.payment import Payment, PaymentVisit
from app.models.service import Service
from app.models.visit import Visit
from app.services.queue_service import queue_service

_REPORT_CURRENCY = "UZS"
_ZERO = Decimal("0.00")


def _gross_payment_report(
    db: Session, start_date: datetime, end_date: datetime, department: str | None,
) -> tuple[list[Row], dict[str, Any]]:
    from app.services.payment_refund_guard import recorded_payment_currency

    links = select(PaymentVisit.id).where(PaymentVisit.payment_id == Payment.id)
    mismatched_link = links.where(or_(
        PaymentVisit.visit_id.is_distinct_from(Payment.visit_id),
        PaymentVisit.amount.is_distinct_from(Payment.amount),
    )).exists()
    link_count = select(func.count(PaymentVisit.id)).where(
        PaymentVisit.payment_id == Payment.id
    ).scalar_subquery()
    verified_department = and_(Visit.id.is_not(None), ~mismatched_link, link_count <= 1)
    # Match the receipt timestamp, including the fallback for historical payments.
    posted_at = func.coalesce(Payment.paid_at, Payment.created_at)
    # A full refund changes the current status but preserves the original receipt.
    # Refunded rows require a recorded posting time to establish that receipt.
    settled_receipt = or_(
        Payment.status.in_(("paid", "completed")),
        and_(Payment.status == "refunded", Payment.paid_at.is_not(None)),
    )
    query = db.query(
        Payment.amount, Payment.currency, Payment.provider, Payment.method,
        posted_at.label("posted_at"), Payment.visit_id, Visit.department,
        verified_department.label("verified_department"),
    ).outerjoin(Visit, Visit.id == Payment.visit_id).filter(
        settled_receipt,
        posted_at >= start_date,
        posted_at <= end_date,
    )
    if department:
        query = query.filter(Visit.department == department)

    by_currency: dict[str, list[Row]] = defaultdict(list)
    unclassified = 0
    unattributed = 0
    for payment in query:
        currency = recorded_payment_currency(payment.currency)
        amount = payment.amount
        if currency is None or not isinstance(amount, Decimal) or not amount.is_finite() or amount < 0:
            unclassified += 1
            continue
        if not payment.verified_department:
            unattributed += 1
            if department:
                continue
        by_currency[currency].append(payment)

    return by_currency.get(_REPORT_CURRENCY, []), {
        "currency": _REPORT_CURRENCY,
        "basis": "gross_settled_payments",
        "unclassified_transactions": unclassified,
        "unattributed_transactions": unattributed,
        "by_currency": {
            currency: {
                "total_revenue": float(sum((payment.amount for payment in payments), _ZERO)),
                "total_transactions": len(payments),
            }
            for currency, payments in sorted(by_currency.items())
        },
    }


def department_ids_for_filter(db: Session, department: str | None) -> list[int] | None:
    """Round-10 (owner P2, PR #3340): resolve a `?department=` filter value
    into Appointment FK ids — the SSOT for EVERY appointment analytics
    surface.

    `Appointment.department` is the ORM RELATIONSHIP (a Department row);
    the historical filters compared it to the request STRING
    (`Appointment.department == department`), which raised ArgumentError
    (500) or silently matched nothing. And the `_stringify_dimension`
    grouping hit Department's numeric `id` attribute first (the model has
    no `name`/`title`/`label`/`code`), so department breakdowns were
    grouped by the surrogate key instead of the canonical `key` contract
    every other surface publishes.

    Contract (exact-key semantics, the same one round-9 gave the schedule
    readers):

    * ``None``/blank parameter → ``None`` — NO filter (unchanged "all
      departments" behavior);
    * known canonical key → ``[departments.id]`` — filter on the FK;
    * unknown key → ``[]`` — an EMPTY result (never "all NULL-department
      rows", which a plain ``department_id == None`` filter would answer).

    Response/grouping labels use the `Appointment.department_key` /
    `department_name` accessors — the string canonical contract.
    """
    if department is None or not str(department).strip():
        return None
    row = db.execute(
        select(Department.id).where(Department.key == str(department).strip())
    ).first()
    return [int(row[0])] if row is not None else []


class AnalyticsService:
    """Сервис для аналитики и статистики клиники"""

    @staticmethod
    def _stringify_dimension(value: Any, fallback: str) -> str:
        """Normalize analytics labels so JSON responses always have string keys."""
        if value is None:
            return fallback
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or fallback
        if isinstance(value, dict):
            for candidate_key in ("name", "title", "label", "code", "id"):
                candidate = value.get(candidate_key)
                if candidate not in (None, ""):
                    return str(candidate)
            return fallback

        for attr_name in ("name", "title", "label", "code", "id"):
            candidate = getattr(value, attr_name, None)
            if candidate not in (None, ""):
                return str(candidate)

        return str(value)

    @staticmethod
    def _visit_activity_date(visit: Visit) -> datetime.date:
        """Resolve the most reliable visit date for analytics."""
        if getattr(visit, "visit_date", None):
            return visit.visit_date
        if getattr(visit, "created_at", None):
            return visit.created_at.date()
        return datetime.now(UTC).date()

    @staticmethod
    def _visit_activity_hour(visit: Visit) -> int:
        """Resolve the most reliable visit hour for analytics."""
        visit_time = getattr(visit, "visit_time", None)
        if visit_time:
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    return datetime.strptime(visit_time, fmt).hour
                except ValueError:
                    continue
        created_at = getattr(visit, "created_at", None)
        if created_at:
            return created_at.hour
        return 0

    @staticmethod
    def get_visit_statistics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: str | None = None,
    ) -> dict[str, Any]:
        """Получение статистики визитов"""
        visit_date_expr = func.coalesce(Visit.visit_date, func.date(Visit.created_at))
        query = db.query(Visit).filter(
            and_(visit_date_expr >= start_date.date(), visit_date_expr <= end_date.date())
        )

        if department:
            query = query.filter(Visit.department == department)

        visits = query.all()

        # Общая статистика
        total_visits = len(visits)
        completed_visits = len([v for v in visits if v.status == "completed"])
        cancelled_visits = len([v for v in visits if v.status == "cancelled"])
        no_show_visits = len([v for v in visits if v.status == "no_show"])

        # Статистика по дням недели
        day_stats = {}
        for visit in visits:
            day_name = calendar.day_name[AnalyticsService._visit_activity_date(visit).weekday()]
            day_stats[day_name] = day_stats.get(day_name, 0) + 1

        # Статистика по часам
        hour_stats = {}
        for visit in visits:
            hour = AnalyticsService._visit_activity_hour(visit)
            hour_stats[hour] = hour_stats.get(hour, 0) + 1

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "total_visits": total_visits,
            "completed_visits": completed_visits,
            "cancelled_visits": cancelled_visits,
            "no_show_visits": no_show_visits,
            "completion_rate": (
                (completed_visits / total_visits * 100) if total_visits > 0 else 0
            ),
            "by_day_of_week": day_stats,
            "by_hour": hour_stats,
        }

    @staticmethod
    def get_patient_statistics(
        db: Session, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Получение статистики пациентов"""
        # Новые пациенты за период
        new_patients = (
            db.query(Patient)
            .filter(
                and_(Patient.created_at >= start_date, Patient.created_at <= end_date)
            )
            .count()
        )

        # Активные пациенты (с визитами за период)
        active_patients = (
            db.query(Visit.patient_id)
            .filter(
                and_(
                    func.coalesce(Visit.visit_date, func.date(Visit.created_at))
                    >= start_date.date(),
                    func.coalesce(Visit.visit_date, func.date(Visit.created_at))
                    <= end_date.date(),
                )
            )
            .distinct()
            .count()
        )

        # Возвращающиеся пациенты
        returning_patients = (
            db.query(Visit.patient_id)
            .filter(
                and_(
                    func.coalesce(Visit.visit_date, func.date(Visit.created_at))
                    >= start_date.date(),
                    func.coalesce(Visit.visit_date, func.date(Visit.created_at))
                    <= end_date.date(),
                )
            )
            .group_by(Visit.patient_id)
            .having(func.count(Visit.id) > 1)
            .count()
        )

        # Статистика по возрастным группам
        patients = (
            db.query(Patient)
            .filter(
                and_(Patient.created_at >= start_date, Patient.created_at <= end_date)
            )
            .all()
        )

        age_groups = {"0-17": 0, "18-30": 0, "31-50": 0, "51-70": 0, "70+": 0}

        current_year = datetime.now().year
        for patient in patients:
            if patient.birth_date:
                age = current_year - patient.birth_date.year
                if age <= 17:
                    age_groups["0-17"] += 1
                elif age <= 30:
                    age_groups["18-30"] += 1
                elif age <= 50:
                    age_groups["31-50"] += 1
                elif age <= 70:
                    age_groups["51-70"] += 1
                else:
                    age_groups["70+"] += 1

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "new_patients": new_patients,
            "active_patients": active_patients,
            "returning_patients": returning_patients,
            "retention_rate": (
                (returning_patients / active_patients * 100)
                if active_patients > 0
                else 0
            ),
            "age_distribution": age_groups,
        }

    @staticmethod
    def calculate_revenue(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: str | None = None,
    ) -> dict[str, Any]:
        """Gross settled receipts, with UZS for the legacy dashboard fields."""
        payments, reporting = _gross_payment_report(db, start_date, end_date, department)
        daily = defaultdict(lambda: _ZERO)
        providers = defaultdict(lambda: _ZERO)
        methods = defaultdict(lambda: _ZERO)
        for payment in payments:
            daily[payment.posted_at.date().isoformat()] += payment.amount
            methods[payment.method or "unknown"] += payment.amount
            if payment.provider:
                providers[payment.provider] += payment.amount

        total = sum((payment.amount for payment in payments), _ZERO)
        transactions = len(payments)
        days = (end_date - start_date).days + 1
        return {
            "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            **reporting,
            "total_revenue": float(total),
            "total_transactions": transactions,
            "average_check": float(round(total / transactions, 2)) if transactions else 0,
            "average_daily_revenue": float(round(total / days, 2)) if days > 0 else 0,
            "daily_revenue": {day: float(amount) for day, amount in sorted(daily.items())},
            "by_provider": {provider: float(amount) for provider, amount in sorted(providers.items())},
            "by_payment_method": {method: float(amount) for method, amount in sorted(methods.items())},
        }

    @staticmethod
    def get_service_statistics(
        db: Session, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Получение статистики услуг"""
        # Получаем все услуги
        services = db.query(Service).all()

        service_stats = {}
        for service in services:
            # Подсчитываем количество визитов с этой услугой
            visit_count = (
                db.query(Visit)
                .filter(
                    and_(
                        func.coalesce(Visit.visit_date, func.date(Visit.created_at))
                        >= start_date.date(),
                        func.coalesce(Visit.visit_date, func.date(Visit.created_at))
                        <= end_date.date(),
                    )
                )
                .join(Visit.services)
                .filter(Service.id == service.id)
                .count()
            )

            service_stats[service.name] = {
                "id": service.id,
                "name": service.name,
                "price": float(service.price) if service.price else 0,
                "visit_count": visit_count,
                "total_revenue": (
                    visit_count * float(service.price) if service.price else 0
                ),
            }

        # Сортируем по популярности
        sorted_services = sorted(
            service_stats.values(), key=lambda x: x["visit_count"], reverse=True
        )

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "total_services": len(services),
            "services": sorted_services,
            "top_services": sorted_services[:5],  # Топ-5 услуг
        }

    @staticmethod
    def get_queue_statistics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: str | None = None,
    ) -> dict[str, Any]:
        """Получение статистики очередей"""
        # Импортируем здесь, чтобы избежать циклических импортов
        from app.models.clinic import Doctor
        from app.models.online_queue import DailyQueue

        # Получаем статистику очередей
        queue_query = db.query(DailyQueue).filter(
            and_(DailyQueue.day >= start_date.date(), DailyQueue.day <= end_date.date())
        )

        if department:
            # D-1 canonical vocabulary: a dental-family department key
            # ('dental') must match canonical 'dentistry' doctors after
            # 0049 (Codex round-5 P2 — exact join filter silently
            # returned no queues).
            # QD-2C (Codex round-7 P2): ресурсные очереди тега
            # (specialist NULL, queue_resource_id) не выпадают из
            # department-отчётов — тег очереди и есть ось «отделения»
            # для ресурс-строк (outerjoin: врач-ось ИЛИ resource-ось,
            # exact-tag против того же словаря variants).
            # QD-2C (Codex round-33 P2): канонические ключи департаментов
            # сидов 0055 ('laboratory', 'echokg') НЕ равны тегам
            # ресурсных очередей ('lab', 'ecg') — D-1 variants их не
            # раскрывают. Соответствие «департамент → теги очередей»
            # живёт в QueueProfile (department_key → queue_tags, как в
            # department overview); profile-теги расширяются D-1
            # variants (зубное семейство) и объединяются с вариантами
            # самого ключа.
            variants = specialty_variants(department)
            from app.models.queue_profile import QueueProfile

            profile_tags: set[str] = set()
            for profile in (
                db.query(QueueProfile)
                .filter(QueueProfile.department_key == department)
                .all()
            ):
                for tag in profile.queue_tags or []:
                    if tag:
                        profile_tags.update(specialty_variants(tag) or [tag])
            resource_tag_values = set(variants) | profile_tags
            queue_query = queue_query.outerjoin(DailyQueue.specialist).filter(
                or_(
                    Doctor.specialty.in_(variants),
                    and_(
                        DailyQueue.queue_resource_id.isnot(None),
                        DailyQueue.queue_tag.in_(resource_tag_values),
                    ),
                )
            )

        queues = queue_query.all()

        total_queues = len(queues)
        total_entries = sum(len(q.entries) for q in queues)
        total_served = sum(
            sum(1 for entry in q.entries if entry.status == "served") for q in queues
        )
        total_waiting = sum(
            sum(
                1
                for entry in q.entries
                if entry.status in {"waiting", "called", "in_service", "diagnostics"}
            )
            for q in queues
        )

        wait_times: list[float] = []
        for queue in queues:
            for entry in queue.entries:
                reference_time = entry.called_at or entry.created_at
                if entry.queue_time and reference_time:
                    wait_times.append(
                        (reference_time - entry.queue_time).total_seconds() / 60
                    )

        avg_wait_time_minutes = round(statistics.mean(wait_times), 2) if wait_times else 0.0
        avg_wait_time = f"{avg_wait_time_minutes:.0f} минут" if avg_wait_time_minutes else "0 минут"

        # Статистика по отделениям
        department_stats = {}
        for queue in queues:
            dept = (
                queue.specialist.specialty
                if getattr(queue, "specialist", None)
                and getattr(queue.specialist, "specialty", None)
                else queue.queue_tag or "Общее"
            )
            if dept not in department_stats:
                department_stats[dept] = {"total_entries": 0, "served": 0, "waiting": 0}

            department_stats[dept]["total_entries"] += len(queue.entries)
            department_stats[dept]["served"] += sum(
                1 for entry in queue.entries if entry.status == "served"
            )
            department_stats[dept]["waiting"] += sum(
                1
                for entry in queue.entries
                if entry.status in {"waiting", "called", "in_service", "diagnostics"}
            )

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "total_queues": total_queues,
            "total_entries": total_entries,
            "total_served": total_served,
            "total_waiting": total_waiting,
            "service_rate": (
                (total_served / total_entries * 100) if total_entries > 0 else 0
            ),
            "average_wait_time_minutes": avg_wait_time_minutes,
            "average_wait_time": avg_wait_time,
            "by_department": department_stats,
        }

    @staticmethod
    def calculate_statistics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: str | None = None,
    ) -> dict[str, Any]:
        """
        Расчёт статистики (SSOT).

        Получение комплексного отчёта со всей статистикой.
        """
        return {
            "report_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "generated_at": queue_service.get_local_timestamp(db).isoformat(),
            },
            "visits": AnalyticsService.get_visit_statistics(
                db, start_date, end_date, department
            ),
            "patients": AnalyticsService.get_patient_statistics(
                db, start_date, end_date
            ),
            "revenue": AnalyticsService.calculate_revenue(
                db, start_date, end_date, department
            ),
            "services": AnalyticsService.get_service_statistics(
                db, start_date, end_date
            ),
            "queues": AnalyticsService.get_queue_statistics(
                db, start_date, end_date, department
            ),
        }

    @staticmethod
    def get_trends(
        db: Session, days: int = 30, *, include_revenue: bool
    ) -> dict[str, Any]:
        """Получение трендов за последние N дней"""
        end_date = queue_service.get_local_timestamp(db).replace(
            hour=0, minute=0, second=0, microsecond=0, fold=0
        )
        start_date = end_date - timedelta(days=days)

        # Тренд визитов
        visit_trend = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            next_date = date + timedelta(days=1)

            visit_count = (
                db.query(Visit)
                .filter(
                    and_(
                        func.coalesce(Visit.visit_date, func.date(Visit.created_at))
                        >= date.date(),
                        func.coalesce(Visit.visit_date, func.date(Visit.created_at))
                        < next_date.date(),
                    )
                )
                .count()
            )

            visit_trend.append(
                {"date": date.strftime("%Y-%m-%d"), "visits": visit_count}
            )

        result: dict[str, Any] = {"period_days": days, "visit_trend": visit_trend}
        if not include_revenue:
            return result

        # Match the visit labels to complete clinic calendar days.
        windows = [(start_date + timedelta(days=i)).astimezone(UTC) for i in range(days + 1)]
        payments, _ = _gross_payment_report(db, windows[0], windows[-1], None)
        totals = [_ZERO] * days
        for payment in payments:
            posted_at = payment.posted_at
            if posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=UTC)
            index = bisect_right(windows, posted_at) - 1
            if 0 <= index < days:
                totals[index] += payment.amount
        result["revenue_trend"] = [
            {"date": item["date"], "revenue": float(total)}
            for item, total in zip(visit_trend, totals, strict=True)
        ]
        return result

    @staticmethod
    def get_payment_provider_analytics(
        db: Session, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Аналитика по провайдерам платежей"""
        from app.models.payment_webhook import PaymentProvider, PaymentTransaction

        # Статистика по провайдерам
        providers = db.query(PaymentProvider).all()
        provider_stats = {}

        for provider in providers:
            # Количество транзакций
            transaction_count = (
                db.query(PaymentTransaction)
                .filter(
                    and_(
                        PaymentTransaction.provider == provider.code,
                        PaymentTransaction.created_at >= start_date,
                        PaymentTransaction.created_at <= end_date,
                    )
                )
                .count()
            )

            # Успешные транзакции
            successful_count = (
                db.query(PaymentTransaction)
                .filter(
                    and_(
                        PaymentTransaction.provider == provider.code,
                        PaymentTransaction.status == "success",
                        PaymentTransaction.created_at >= start_date,
                        PaymentTransaction.created_at <= end_date,
                    )
                )
                .count()
            )

            # Общая сумма
            total_amount = (
                db.query(func.sum(PaymentTransaction.amount))
                .filter(
                    and_(
                        PaymentTransaction.provider == provider.code,
                        PaymentTransaction.status == "success",
                        PaymentTransaction.created_at >= start_date,
                        PaymentTransaction.created_at <= end_date,
                    )
                )
                .scalar()
                or 0
            )

            # Средняя сумма транзакции
            avg_amount = total_amount / successful_count if successful_count > 0 else 0

            provider_stats[provider.code] = {
                "name": provider.name,
                "is_active": provider.is_active,
                "total_transactions": transaction_count,
                "successful_transactions": successful_count,
                "failed_transactions": transaction_count - successful_count,
                "success_rate": (
                    (successful_count / transaction_count * 100)
                    if transaction_count > 0
                    else 0
                ),
                "total_amount": total_amount,
                "average_amount": avg_amount,
                "commission_earned": (
                    total_amount * (provider.commission_percent / 100)
                    if provider.commission_percent
                    else 0
                ),
            }

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "providers": provider_stats,
            "summary": {
                "total_providers": len(providers),
                "active_providers": len([p for p in providers if p.is_active]),
                "total_transactions": sum(
                    stats["total_transactions"] for stats in provider_stats.values()
                ),
                "total_revenue": sum(
                    stats["total_amount"] for stats in provider_stats.values()
                ),
                "total_commission": sum(
                    stats["commission_earned"] for stats in provider_stats.values()
                ),
            },
        }

    @staticmethod
    def get_appointment_flow_analytics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: str | None = None,
    ) -> dict[str, Any]:
        """Аналитика потока записей (appointments)"""

        query = db.query(Appointment).filter(
            and_(
                Appointment.appointment_date >= start_date.date(),
                Appointment.appointment_date <= end_date.date(),
            )
        )

        # Round-10 (owner P2, PR #3340): the filter is the canonical KEY
        # string — resolve it to the FK ids ONCE (see
        # department_ids_for_filter); the old
        # `Appointment.department == department` compared the ORM
        # RELATIONSHIP to the request string (ArgumentError → 500 on the
        # first keyed query). An unknown key answers an EMPTY analytics
        # payload (exact-key semantics), never the unfiltered result.
        department_ids = department_ids_for_filter(db, department)
        if department_ids is not None:
            query = query.filter(Appointment.department_id.in_(department_ids))

        appointments = query.all()

        # Статистика по статусам
        status_stats = {}
        for appointment in appointments:
            status = AnalyticsService._stringify_dimension(
                getattr(appointment, "status", None), "scheduled"
            )
            if status not in status_stats:
                status_stats[status] = 0
            status_stats[status] += 1

        # Статистика по отделениям
        # Round-10 (owner P2): group under the canonical KEY string —
        # `_stringify_dimension(appointment.department, ...)` walked the
        # Department row's attrs (no name/title/label/code) into the
        # numeric `id` fallback, so the breakdown was keyed by the
        # surrogate PK instead of the `cardio`-style contract.
        department_stats = {}
        for appointment in appointments:
            dept = getattr(appointment, "department_key", None) or "Не указано"
            if dept not in department_stats:
                department_stats[dept] = {"total": 0, "paid": 0, "completed": 0}
            department_stats[dept]["total"] += 1

            if appointment.status == "paid":
                department_stats[dept]["paid"] += 1
            elif appointment.status == "completed":
                department_stats[dept]["completed"] += 1

        # Статистика по дням недели
        day_stats = {}
        for appointment in appointments:
            day_name = calendar.day_name[appointment.appointment_date.weekday()]
            if day_name not in day_stats:
                day_stats[day_name] = 0
            day_stats[day_name] += 1

        # Конверсия по воронке
        total_appointments = len(appointments)
        paid_appointments = len([a for a in appointments if a.status == "paid"])
        completed_appointments = len(
            [a for a in appointments if a.status == "completed"]
        )

        conversion_rates = {
            "pending_to_paid": (
                (paid_appointments / total_appointments * 100)
                if total_appointments > 0
                else 0
            ),
            "paid_to_completed": (
                (completed_appointments / paid_appointments * 100)
                if paid_appointments > 0
                else 0
            ),
            "overall_conversion": (
                (completed_appointments / total_appointments * 100)
                if total_appointments > 0
                else 0
            ),
        }

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_appointments": total_appointments,
                "paid_appointments": paid_appointments,
                "completed_appointments": completed_appointments,
                "cancelled_appointments": len(
                    [a for a in appointments if a.status == "cancelled"]
                ),
                "no_show_appointments": len(
                    [a for a in appointments if a.status == "no_show"]
                ),
            },
            "status_distribution": status_stats,
            "department_performance": department_stats,
            "day_of_week_distribution": day_stats,
            "conversion_rates": conversion_rates,
        }

    @staticmethod
    def get_revenue_breakdown_analytics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: str | None = None,
    ) -> dict[str, Any]:
        """Break down the same settled ledger used by the default dashboard."""
        payments, reporting = _gross_payment_report(db, start_date, end_date, department)
        daily = defaultdict(lambda: _ZERO)
        provider_amounts = defaultdict(lambda: _ZERO)
        provider_counts = defaultdict(int)
        department_amounts = defaultdict(lambda: _ZERO)
        department_visits = defaultdict(set)
        for payment in payments:
            daily[payment.posted_at.date().isoformat()] += payment.amount
            if payment.provider:
                provider_amounts[payment.provider] += payment.amount
                provider_counts[payment.provider] += 1
            if payment.verified_department:
                key = payment.department or "Общее"
                department_amounts[key] += payment.amount
                department_visits[key].add(payment.visit_id)

        total = sum((payment.amount for payment in payments), _ZERO)
        transactions = len(payments)
        return {
            "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            **reporting,
            "total_revenue": float(total),
            "total_transactions": transactions,
            "average_transaction": float(round(total / transactions, 2)) if transactions else 0,
            "provider_breakdown": {
                provider: {
                    "count": provider_counts[provider],
                    "total_amount": float(amount),
                    "average_amount": float(round(amount / provider_counts[provider], 2)),
                }
                for provider, amount in sorted(provider_amounts.items())
            },
            "provider_totals": {
                "total_transactions": sum(provider_counts.values()),
                "total_revenue": float(sum(provider_amounts.values(), _ZERO)),
            },
            "department_breakdown": {
                key: {"visits": len(department_visits[key]), "total_revenue": float(amount)}
                for key, amount in sorted(department_amounts.items())
            },
            "daily_revenue": [
                {"date": day, "amount": float(amount)} for day, amount in sorted(daily.items())
            ],
        }

    @staticmethod
    def generate_report(
        db: Session,
        report_type: str,
        start_date: datetime,
        end_date: datetime,
        department: str | None = None,
        format: str = "json",
    ) -> dict[str, Any]:
        """
        Генерация отчёта (SSOT).

        Args:
            db: Сессия БД
            report_type: Тип отчёта (revenue|visits|patients|services|comprehensive)
            start_date: Начальная дата
            end_date: Конечная дата
            department: Отделение (опционально)
            format: Формат отчёта (json|html|csv)

        Returns:
            Dict с данными отчёта
        """
        if report_type == "revenue":
            report_data = AnalyticsService.calculate_revenue(
                db, start_date, end_date, department
            )
        elif report_type == "visits":
            report_data = AnalyticsService.get_visit_statistics(
                db, start_date, end_date, department
            )
        elif report_type == "patients":
            report_data = AnalyticsService.get_patient_statistics(
                db, start_date, end_date
            )
        elif report_type == "services":
            report_data = AnalyticsService.get_service_statistics(
                db, start_date, end_date
            )
        elif report_type == "comprehensive":
            report_data = AnalyticsService.calculate_statistics(
                db, start_date, end_date, department
            )
        else:
            raise ValueError(f"Неизвестный тип отчёта: {report_type}")

        # Добавляем метаданные
        report_data["report_meta"] = {
            "report_type": report_type,
            "format": format,
            "generated_at": queue_service.get_local_timestamp(db).isoformat(),
        }

        return report_data

    @staticmethod
    def export_report(
        db: Session,
        report_type: str,
        start_date: datetime,
        end_date: datetime,
        department: str | None = None,
        export_format: str = "json",
    ) -> bytes:
        """
        Экспорт отчёта (SSOT).

        Args:
            db: Сессия БД
            report_type: Тип отчёта
            start_date: Начальная дата
            end_date: Конечная дата
            department: Отделение (опционально)
            export_format: Формат экспорта (json|csv|excel)

        Returns:
            bytes - данные отчёта в выбранном формате
        """
        import csv
        import json
        from io import BytesIO, StringIO

        # Генерируем отчёт
        report_data = AnalyticsService.generate_report(
            db, report_type, start_date, end_date, department, format="json"
        )

        if export_format == "json":
            return json.dumps(report_data, ensure_ascii=False, indent=2).encode('utf-8')

        elif export_format == "csv":
            # Преобразуем данные в CSV
            output = StringIO()
            writer = csv.writer(output)

            # Заголовки
            writer.writerow(["Период", "Начало", "Конец"])
            writer.writerow(
                [
                    report_data.get("period", {}).get("start_date", ""),
                    report_data.get("period", {}).get("end_date", ""),
                ]
            )

            # Основные данные (упрощённая версия)
            if "total_revenue" in report_data:
                writer.writerow(["Общий доход", report_data["total_revenue"]])
            if "total_visits" in report_data:
                writer.writerow(["Всего визитов", report_data["total_visits"]])

            return output.getvalue().encode('utf-8')

        elif export_format == "excel":
            # Для Excel нужен pandas
            try:
                from io import BytesIO

                import pandas as pd

                # Преобразуем данные в DataFrame
                df = pd.DataFrame([report_data])
                output = BytesIO()
                df.to_excel(output, index=False, engine='openpyxl')
                return output.getvalue()
            except ImportError:
                raise ValueError("Для экспорта в Excel требуется pandas и openpyxl")

        else:
            raise ValueError(f"Неподдерживаемый формат экспорта: {export_format}")


# Создаём глобальный экземпляр сервиса
analytics_service = AnalyticsService()
