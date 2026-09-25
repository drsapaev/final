from __future__ import annotations

from typing import Any

from app.api.v1.endpoints.registrar_integration._helpers import *  # noqa
from app.models.clinic import Schedule
from app.models.online_queue import QueueResource
from app.services.registrar_doctor_eligibility import (
    accepted_specialty_variants_for_department_key,
    doctor_booking_unavailable_reason,
    is_named_eligible_real_doctor,
    service_requires_doctor_selection,
)


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

        # One registry read for the whole catalog; exact active tags are the
        # same routing truth the cart command checks before saving.
        active_resource_tags = {
            tag
            for (tag,) in (
                db.query(QueueResource.queue_tag)
                .filter(QueueResource.active.is_(True))
                .all()
            )
        }

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
                # RQ-05 (F-04): каталог регистратуры обязан передавать
                # requires_doctor, чтобы выбор врача был обязательным ровно
                # там, где его требует сервер (S-03).
                "requires_doctor": bool(
                    getattr(service, 'requires_doctor', False)
                ),
                "doctor_selection_required": service_requires_doctor_selection(
                    service
                ),
                "doctor_booking_available": doctor_booking_unavailable_reason(
                    service, active_resource_tags
                ) is None,
                "group": None,  # Добавим группу для frontend
            }

            # RQ-08.a: серверная eligibility для UI-фильтра врачей
            # (frontend filterDoctorsForService): допустимые специальности
            # врача из SSOT DOCTOR_QUEUE_SPECIALTY_VARIANTS. None — проверка
            # неприменима, семантика ровно как в гейте RQ-05.a.
            # Codex P1 #3311: источник department_key — ТОТ ЖЕ, что читает
            # гейт корзины (поле Service.department_key), а НЕ link-priority
            # service_data["department_key"]: при расхождении DepartmentService-
            # связи и поля услуги (админ-эндпоинт это позволяет) UI обязан
            # зеркалить именно серверный запрет, иначе предложит врача,
            # которого POST /registrar/cart отклонит.
            _accepted = accepted_specialty_variants_for_department_key(
                getattr(service, 'department_key', None)
            )
            service_data["accepted_specialties"] = (
                sorted(_accepted) if _accepted is not None else None
            )

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
        # QD-1.1 (queue resource role cleanup, Codex round-4 P2): the
        # registrar doctor selector hides synthetic queue-resource rows —
        # picking one would fail booking eligibility with a guaranteed 409.
        # The CRUD method defaults to a 100-row cap. Page its canonical
        # eligibility query so every active real doctor reaches the wizard,
        # including those after incomplete/internal profiles in ID order.
        doctors = []
        page_size = 100
        while True:
            page = crud_clinic.get_doctors(
                db,
                skip=len(doctors),
                limit=page_size,
                active_only=True,
                eligible_only=True,
                exclude_internal_only=True,
            )
            doctors.extend(page)
            if len(page) < page_size:
                break

        owner_ids = [doctor.user_id for doctor in doctors if doctor.user_id]
        owners = (
            {
                owner.id: owner
                for owner in db.query(User).filter(User.id.in_(owner_ids)).all()
            }
            if owner_ids
            else {}
        )
        # A registration card must identify a named, active clinician.
        # Historical orphaned profiles and blank names need admin repair.
        doctors = [
            doctor
            for doctor in doctors
            if is_named_eligible_real_doctor(doctor, owners.get(doctor.user_id))
        ]

        if specialty:
            # D-1 canonical vocabulary: match any dental-family spelling
            # ("dental" filter must find canonical "dentistry" rows and
            # vice versa) instead of the historical exact comparison.
            wanted = accepted_specialty_variants_for_department_key(specialty) or set()
            doctors = [
                doctor
                for doctor in doctors
                if (doctor.specialty or "").strip().lower() in wanted
            ]

        schedules_by_doctor: dict[int, list[Schedule]] = {}
        if with_schedule and doctors:
            for schedule in (
                db.query(Schedule)
                .filter(
                    Schedule.doctor_id.in_([doctor.id for doctor in doctors]),
                    Schedule.active.is_(True),
                )
                .order_by(Schedule.doctor_id, Schedule.weekday)
                .all()
            ):
                schedules_by_doctor.setdefault(schedule.doctor_id, []).append(schedule)

        result = []
        for doctor in doctors:
            owner = owners[doctor.user_id]
            doctor_data = {
                "id": doctor.id,
                "user_id": doctor.user_id,
                "full_name": owner.full_name.strip(),
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet,
                "price_default": (
                    float(doctor.price_default) if doctor.price_default else 0
                ),
                "start_number_online": doctor.start_number_online,
                "max_online_per_day": doctor.max_online_per_day,
                "user": (
                    {
                        "full_name": owner.full_name.strip(),
                        "username": owner.username,
                    }
                ),
            }

            if with_schedule:
                schedules = schedules_by_doctor.get(doctor.id, [])
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
