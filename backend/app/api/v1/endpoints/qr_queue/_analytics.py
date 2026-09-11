"""Split from qr_queue.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.qr_queue._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.qr_queue._helpers import router


@router.get("/admin/queue-analytics/{specialist_id}", response_model=dict[str, Any])
def get_queue_analytics(
    specialist_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получает аналитику по очередям специалиста
    Доступно только администраторам
    """
    # Парсим даты
    start_dt = None
    end_dt = None

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат start_date. Используйте YYYY-MM-DD",
            )

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат end_date. Используйте YYYY-MM-DD",
            )

    # Codex round-39 P2: дефолтные границы периода — КЛИНИК-локальный
    # день (clinic_today SSOT, таймзона настроек очередей): строки
    # статистики штампуются клиник-днём (round-38), и host date.today()
    # в окне расхождения 19:00-24:00Z исключал текущий клиник-день из
    # дефолтного 30-дневного периода.
    from app.crud.clinic import clinic_today

    clinic_day = clinic_today(db)

    # Если даты не указаны, берем последние 30 дней
    if not start_dt:
        start_dt = clinic_day - timedelta(days=30)
    if not end_dt:
        end_dt = clinic_day

    # QD-2C (Codex round-11 P2): specialist's registry tag — include the
    # resource-axis rows (specialist NULL, queue_resource_id) in the
    # HISTORICAL filter: the lab/ecg activity moved onto the resource
    # surface, so a doctor-only join would return zero totals for the
    # legacy specialist id despite recorded resource-queue rows.
    from sqlalchemy import and_, or_

    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, QueueStatistics

    queue_filter = DailyQueue.specialist_id == specialist_id
    doctor_row = db.query(Doctor).filter(Doctor.id == specialist_id).first()
    if doctor_row is not None and doctor_row.specialty:
        queue_filter = or_(
            DailyQueue.specialist_id == specialist_id,
            and_(
                DailyQueue.queue_resource_id.isnot(None),
                DailyQueue.queue_tag == doctor_row.specialty,
            ),
        )

    # Получаем статистику
    stats = (
        db.query(QueueStatistics)
        .join(DailyQueue)
        .filter(
            queue_filter,
            QueueStatistics.date >= start_dt,
            QueueStatistics.date <= end_dt,
        )
        .all()
    )

    # Агрегируем данные
    total_online_joins = sum(s.online_joins for s in stats)
    total_desk_registrations = sum(s.desk_registrations for s in stats)
    total_telegram_joins = sum(s.telegram_joins for s in stats)
    total_confirmation_joins = sum(s.confirmation_joins for s in stats)
    total_served = sum(s.total_served for s in stats)
    total_no_show = sum(s.total_no_show for s in stats)

    avg_wait_time = None
    if stats:
        wait_times = [s.average_wait_time for s in stats if s.average_wait_time]
        if wait_times:
            avg_wait_time = sum(wait_times) / len(wait_times)

    return {
        "specialist_id": specialist_id,
        "period": {"start_date": start_dt.isoformat(), "end_date": end_dt.isoformat()},
        "totals": {
            "online_joins": total_online_joins,
            "desk_registrations": total_desk_registrations,
            "telegram_joins": total_telegram_joins,
            "confirmation_joins": total_confirmation_joins,
            "total_served": total_served,
            "total_no_show": total_no_show,
        },
        "metrics": {
            "average_wait_time": avg_wait_time,
            "no_show_rate": (
                (total_no_show / (total_served + total_no_show)) * 100
                if (total_served + total_no_show) > 0
                else 0
            ),
        },
        "daily_stats": [
            {
                "date": stat.date.isoformat(),
                "online_joins": stat.online_joins,
                "desk_registrations": stat.desk_registrations,
                "telegram_joins": stat.telegram_joins,
                "confirmation_joins": stat.confirmation_joins,
                "total_served": stat.total_served,
                "total_no_show": stat.total_no_show,
                "average_wait_time": stat.average_wait_time,
                "peak_hour": stat.peak_hour,
                "max_queue_length": stat.max_queue_length,
            }
            for stat in stats
        ],
    }


# ===================== ОБНОВЛЕНИЕ ОНЛАЙН ЗАПИСИ =====================


class UpdateOnlineEntryRequest(BaseModel):
    """Запрос на обновление данных онлайн записи"""

    patient_name: str | None = None
    phone: str | None = None
    birth_year: int | None = None
    address: str | None = None


