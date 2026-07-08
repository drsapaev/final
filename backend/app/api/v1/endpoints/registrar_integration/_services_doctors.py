from __future__ import annotations

from app.api.v1.endpoints.registrar_integration._helpers import *  # noqa

from typing import Any
@router.get("/registrar/services", response_model=dict[str, Any])
def get_registrar_services(
    specialty: str | None = Query(None, description="Фильтр по специальности"),
    active_only: bool = Query(True, description="Только активные услуги"),
    db: Session = Depends(get_db),
    # Разрешаем доступ также профильным ролям врачей
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Doctor",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Получить услуги для регистратуры из справочника админ панели
    Из detail.md стр. 112: "Услуги (чек‑лист, группами — дерма/косметология/кардио/ЭКГ/ЭхоКГ/стоматология/лаборатория)"
    """
    try:
        # Получаем категории услуг
        categories = crud_clinic.get_service_categories(
            db, specialty=specialty, active_only=active_only
        )

        # Получаем услуги из основной таблицы
        query = db.query(Service)

        if active_only:
            query = query.filter(Service.active == True)

        services = query.all()

        # Получаем маппинг услуг к отделениям
        dept_services = (
            db.query(DepartmentService)
            .options(
                # joinedload(DepartmentService.department) # Если нужно
            )
            .all()
        )

        # Создаем словарь service_id -> department_key
        service_dept_map = {}
        for ds in dept_services:
            # Загружаем department если он не загружен (lazy load)
            if ds.department:
                service_dept_map[ds.service_id] = ds.department.key

        # Группируем услуги по категориям согласно документации
        grouped_services = {
            "laboratory": [],  # L - Лабораторные анализы
            "dermatology": [],  # D - Дерматологические услуги
            "cosmetology": [],  # C - Косметологические услуги
            "cardiology": [],  # K - Кардиология
            "stomatology": [],  # S - Стоматология
            "procedures": [],  # O - Прочие процедуры
        }
        queue_group_to_registrar_group = {
            "cardiology": "cardiology",
            "ecg": "cardiology",
            "dermatology": "dermatology",
            "dental": "stomatology",
            "laboratory": "laboratory",
            "procedures": "procedures",
        }

        # Простая логика распределения услуг по трём группам
        for service in services:
            service_data = {
                "id": service.id,
                "name": service.name,
                "code": service.service_code or get_service_code(service.id, db),
                "price": float(service.price) if service.price else 0,
                "currency": service.currency or "UZS",
                "duration_minutes": service.duration_minutes or 30,
                "category_id": service.category_id,
                "doctor_id": service.doctor_id,
                "department_key": service_dept_map.get(service.id)
                or getattr(
                    service, 'department_key', None
                ),  # [OK] Берем из маппинга или поля
                # [OK] НОВЫЕ ПОЛЯ ДЛЯ КЛАССИФИКАЦИИ
                "category_code": getattr(service, 'category_code', None),
                "service_code": getattr(service, 'service_code', None),
                "queue_tag": getattr(
                    service, 'queue_tag', None
                ),  # [TARGET] ДОБАВЛЯЕМ queue_tag ДЛЯ ЭКГ!
                "is_consultation": getattr(
                    service, 'is_consultation', False
                ),  # Добавляем поле is_consultation
                "group": None,  # Добавим группу для frontend
            }

            # [OK] НОВАЯ ЛОГИКА: определяем группу только по явному routing truth
            resolved_queue_group = resolve_queue_group_key(
                service_code=service_data["service_code"],
                queue_tag=service_data["queue_tag"],
                department_key=service_data["department_key"],
            )

            if resolved_queue_group:
                registrar_group = queue_group_to_registrar_group.get(
                    resolved_queue_group, "procedures"
                )
                service_data["group"] = registrar_group
                grouped_services[registrar_group].append(service_data)
                continue

            # Без явного routing truth держим нейтральную группу, а не угадываем по category/name.
            service_data["group"] = "procedures"
            grouped_services["procedures"].append(service_data)

        return {
            "services_by_group": grouped_services,
            "categories": [
                {
                    "id": cat.id,
                    "code": cat.code,
                    "name_ru": cat.name_ru,
                    "name_uz": cat.name_uz,
                    "specialty": cat.specialty,
                }
                for cat in categories
            ],
            "total_services": len(services),
        }

    except (ValueError, AttributeError):
        # Ошибки валидации или доступа к атрибутам
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )
    except Exception as e:
        # Остальные ошибки (БД, сеть и т.д.)
        from sqlalchemy.exc import SQLAlchemyError

        if isinstance(e, SQLAlchemyError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка сервера. Подробности в журнале.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== ВРАЧИ И РАСПИСАНИЯ =====================


@router.get("/registrar/doctors", response_model=dict[str, Any])
def get_registrar_doctors(
    specialty: str | None = Query(None, description="Фильтр по специальности"),
    with_schedule: bool = Query(True, description="Включить расписание"),
    db: Session = Depends(get_db),
    # Разрешаем доступ также профильным ролям врачей
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Doctor",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Получить врачей с расписаниями для регистратуры
    Из detail.md стр. 106: "Специалист/Кабинет"
    """
    try:
        doctors = crud_clinic.get_doctors(db, active_only=True)

        if specialty:
            doctors = [d for d in doctors if d.specialty == specialty]

        result = []
        for doctor in doctors:
            doctor_data = {
                "id": doctor.id,
                "user_id": doctor.user_id,
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet,
                "price_default": (
                    float(doctor.price_default) if doctor.price_default else 0
                ),
                "start_number_online": doctor.start_number_online,
                "max_online_per_day": doctor.max_online_per_day,
                "user": (
                    {
                        "full_name": (
                            doctor.user.full_name
                            if doctor.user
                            else f"Врач #{doctor.id}"
                        ),
                        "username": doctor.user.username if doctor.user else None,
                    }
                    if doctor.user
                    else None
                ),
            }

            if with_schedule:
                schedules = crud_clinic.get_doctor_schedules(db, doctor.id)
                doctor_data["schedules"] = [
                    {
                        "id": schedule.id,
                        "weekday": schedule.weekday,
                        "start_time": (
                            schedule.start_time.strftime("%H:%M")
                            if schedule.start_time
                            else None
                        ),
                        "end_time": (
                            schedule.end_time.strftime("%H:%M")
                            if schedule.end_time
                            else None
                        ),
                        "breaks": schedule.breaks,
                        "active": schedule.active,
                    }
                    for schedule in schedules
                ]

            result.append(doctor_data)

        return {
            "doctors": result,
            "total_doctors": len(result),
            "by_specialty": {
                specialty: len([d for d in result if d["specialty"] == specialty])
                for specialty in {d["specialty"] for d in result}
            },
        }

    except (ValueError, AttributeError):
        # Ошибки валидации или доступа к атрибутам
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )
    except Exception as e:
        # Остальные ошибки (БД, сеть и т.д.)
        from sqlalchemy.exc import SQLAlchemyError

        if isinstance(e, SQLAlchemyError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка сервера. Подробности в журнале.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== НАСТРОЙКИ ОЧЕРЕДИ ДЛЯ РЕГИСТРАТУРЫ =====================

