from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.services import online_queue

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("/status", summary="Статус очереди")
async def get_queue_status(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    department: str = Query(..., description="Отделение"),
    date_str: str = Query(..., description="Дата (YYYY-MM-DD)"),
):
    """
    Получить текущий статус очереди для отделения на конкретную дату
    """
    try:
        stats = online_queue.load_stats(db, department=department, date_str=date_str)
        return {
            "department": department,
            "date": date_str,
            "is_open": stats.is_open,
            "start_number": stats.start_number,
            "last_ticket": stats.last_ticket,
            "waiting": stats.waiting,
            "serving": stats.serving,
            "done": stats.done,
            "total": stats.waiting + stats.serving + stats.done,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения статуса очереди: {str(e)}"
        )


@router.post("/open", summary="Открыть очередь")
async def open_queue(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar")),
    department: str = Query(..., description="Отделение"),
    date_str: str = Query(..., description="Дата (YYYY-MM-DD)"),
    start_number: int = Query(1, ge=1, description="Начальный номер талона"),
):
    """
    Открыть очередь для отделения на конкретную дату
    """
    try:
        # Открываем день
        online_queue.get_or_create_day(
            db, department=department, date_str=date_str, open_flag=True
        )

        # Устанавливаем начальный номер
        online_queue._set_int(
            db, online_queue._k(department, date_str, "start_number"), start_number
        )
        online_queue._set_int(
            db, online_queue._k(department, date_str, "last_ticket"), start_number - 1
        )
        online_queue._set_int(db, online_queue._k(department, date_str, "waiting"), 0)
        online_queue._set_int(db, online_queue._k(department, date_str, "serving"), 0)
        online_queue._set_int(db, online_queue._k(department, date_str, "done"), 0)

        db.commit()

        # Отправляем broadcast через WebSocket
        try:
            stats = online_queue.load_stats(
                db, department=department, date_str=date_str
            )
            online_queue._broadcast(department, date_str, stats)
        except Exception as e:
            print(f"⚠️ WebSocket broadcast error: {e}")

        return {
            "message": "Очередь успешно открыта",
            "department": department,
            "date": date_str,
            "start_number": start_number,
            "is_open": True,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Ошибка открытия очереди: {str(e)}"
        )


@router.post("/close", summary="Закрыть очередь")
async def close_queue(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar")),
    department: str = Query(..., description="Отделение"),
    date_str: str = Query(..., description="Дата (YYYY-MM-DD)"),
):
    """
    Закрыть очередь для отделения на конкретную дату
    """
    try:
        # Закрываем день
        online_queue.get_or_create_day(
            db, department=department, date_str=date_str, open_flag=False
        )

        db.commit()

        # Отправляем broadcast через WebSocket
        try:
            stats = online_queue.load_stats(
                db, department=department, date_str=date_str
            )
            online_queue._broadcast(department, date_str, stats)
        except Exception as e:
            print(f"⚠️ WebSocket broadcast error: {e}")

        return {
            "message": "Очередь успешно закрыта",
            "department": department,
            "date": date_str,
            "is_open": False,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Ошибка закрытия очереди: {str(e)}"
        )


@router.post("/next", summary="Следующий пациент")
async def call_next_patient(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    department: str = Query(..., description="Отделение"),
    date_str: str = Query(..., description="Дата (YYYY-MM-DD)"),
):
    """
    Вызвать следующего пациента из очереди
    """
    try:
        # Получаем текущий статус
        stats = online_queue.load_stats(db, department=department, date_str=date_str)

        if not stats.is_open:
            raise HTTPException(status_code=400, detail="Очередь закрыта")

        if stats.waiting == 0:
            raise HTTPException(status_code=400, detail="В очереди нет пациентов")

        # Уменьшаем количество ожидающих
        waiting = max(0, stats.waiting - 1)
        online_queue._set_int(
            db, online_queue._k(department, date_str, "waiting"), waiting
        )

        # Увеличиваем количество обслуживаемых
        serving = stats.serving + 1
        online_queue._set_int(
            db, online_queue._k(department, date_str, "serving"), serving
        )

        db.commit()

        # Отправляем broadcast через WebSocket
        try:
            updated_stats = online_queue.load_stats(
                db, department=department, date_str=date_str
            )
            online_queue._broadcast(department, date_str, updated_stats)
        except Exception as e:
            print(f"⚠️ WebSocket broadcast error: {e}")

        return {
            "message": "Следующий пациент вызван",
            "department": department,
            "date": date_str,
            "waiting": waiting,
            "serving": serving,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка вызова пациента: {str(e)}")


@router.post("/complete", summary="Завершить прием")
async def complete_patient(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    department: str = Query(..., description="Отделение"),
    date_str: str = Query(..., description="Дата (YYYY-MM-DD)"),
):
    """
    Завершить прием пациента
    """
    try:
        # Получаем текущий статус
        stats = online_queue.load_stats(db, department=department, date_str=date_str)

        if not stats.is_open:
            raise HTTPException(status_code=400, detail="Очередь закрыта")

        if stats.serving == 0:
            raise HTTPException(status_code=400, detail="Нет пациентов на приеме")

        # Уменьшаем количество обслуживаемых
        serving = max(0, stats.serving - 1)
        online_queue._set_int(
            db, online_queue._k(department, date_str, "serving"), serving
        )

        # Увеличиваем количество завершенных
        done = stats.done + 1
        online_queue._set_int(db, online_queue._k(department, date_str, "done"), done)

        db.commit()

        # Отправляем broadcast через WebSocket
        try:
            updated_stats = online_queue.load_stats(
                db, department=department, date_str=date_str
            )
            online_queue._broadcast(department, date_str, updated_stats)
        except Exception as e:
            print(f"⚠️ WebSocket broadcast error: {e}")

        return {
            "message": "Прием пациента завершен",
            "department": department,
            "date": date_str,
            "serving": serving,
            "done": done,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Ошибка завершения приема: {str(e)}"
        )


@router.post("/add", summary="Добавить пациента в очередь")
async def add_to_queue(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar")),
    department: str = Query(..., description="Отделение"),
    date_str: str = Query(..., description="Дата (YYYY-MM-DD)"),
    patient_name: str = Query(..., description="Имя пациента"),
    priority: bool = Query(False, description="Приоритетная очередь"),
):
    """
    Добавить пациента в очередь
    """
    try:
        # Получаем текущий статус
        stats = online_queue.load_stats(db, department=department, date_str=date_str)

        if not stats.is_open:
            raise HTTPException(status_code=400, detail="Очередь закрыта")

        # Генерируем следующий номер талона
        next_ticket = stats.last_ticket + 1
        online_queue._set_int(
            db, online_queue._k(department, date_str, "last_ticket"), next_ticket
        )

        # Увеличиваем количество ожидающих
        waiting = stats.waiting + 1
        online_queue._set_int(
            db, online_queue._k(department, date_str, "waiting"), waiting
        )

        db.commit()

        # Отправляем broadcast через WebSocket
        try:
            updated_stats = online_queue.load_stats(
                db, department=department, date_str=date_str
            )
            online_queue._broadcast(department, date_str, updated_stats)
        except Exception as e:
            print(f"⚠️ WebSocket broadcast error: {e}")

        return {
            "message": "Пациент добавлен в очередь",
            "department": department,
            "date": date_str,
            "ticket_number": next_ticket,
            "patient_name": patient_name,
            "priority": priority,
            "waiting": waiting,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Ошибка добавления в очередь: {str(e)}"
        )


@router.get("/departments", summary="Список отделений с очередями")
async def get_queue_departments(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    date_str: Optional[str] = Query(None, description="Дата (YYYY-MM-DD)"),
):
    """
    Получить список отделений с информацией об очередях
    """
    try:
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # Получаем список отделений из настроек
        dept_stmt = db.execute(
            "SELECT DISTINCT SUBSTRING_INDEX(key, '::', 1) as dept FROM settings WHERE category = 'queue' AND key LIKE '%::%'"
        )
        departments = [row[0] for row in dept_stmt.fetchall() if row[0]]

        result = []
        for dept in departments:
            try:
                stats = online_queue.load_stats(db, department=dept, date_str=date_str)
                dept_info = {
                    "department": dept,
                    "date": date_str,
                    "is_open": stats.is_open,
                    "start_number": stats.start_number,
                    "last_ticket": stats.last_ticket,
                    "waiting": stats.waiting,
                    "serving": stats.serving,
                    "done": stats.done,
                    "total": stats.waiting + stats.serving + stats.done,
                }
                result.append(dept_info)
            except Exception as e:
                # Если не удалось загрузить статистику для отделения, пропускаем
                print(f"⚠️ Ошибка загрузки статистики для {dept}: {e}")
                continue

        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения списка отделений: {str(e)}"
        )


@router.get("/history", summary="История очереди")
async def get_queue_history(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar")),
    department: str = Query(..., description="Отделение"),
    date_from: str = Query(..., description="Дата начала (YYYY-MM-DD)"),
    date_to: str = Query(..., description="Дата окончания (YYYY-MM-DD)"),
):
    """
    Получить историю очереди за период
    """
    try:
        # Парсим даты
        start_date = datetime.strptime(date_from, "%Y-%m-%d").date()
        end_date = datetime.strptime(date_to, "%Y-%m-%d").date()

        if start_date > end_date:
            raise HTTPException(
                status_code=400, detail="Дата начала не может быть позже даты окончания"
            )

        history = []
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            try:
                stats = online_queue.load_stats(
                    db, department=department, date_str=date_str
                )
                day_history = {
                    "date": date_str,
                    "is_open": stats.is_open,
                    "start_number": stats.start_number,
                    "last_ticket": stats.last_ticket,
                    "waiting": stats.waiting,
                    "serving": stats.serving,
                    "done": stats.done,
                    "total": stats.waiting + stats.serving + stats.done,
                }
                history.append(day_history)
            except Exception as e:
                # Если не удалось загрузить статистику для дня, добавляем пустую запись
                day_history = {
                    "date": date_str,
                    "is_open": False,
                    "start_number": 0,
                    "last_ticket": 0,
                    "waiting": 0,
                    "serving": 0,
                    "done": 0,
                    "total": 0,
                }
                history.append(day_history)

            current_date += timedelta(days=1)

        return {
            "department": department,
            "date_from": date_from,
            "date_to": date_to,
            "history": history,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения истории очереди: {str(e)}"
        )
