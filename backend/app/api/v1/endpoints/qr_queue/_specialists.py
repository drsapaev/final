"""Split from qr_queue.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.qr_queue._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.qr_queue._helpers import router


@router.get("/available-specialists", response_model=dict[str, Any])
def get_available_specialists(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
):
    """
    Получает список доступных специалистов для QR-регистрации (публичный эндпоинт)
    Используется для динамического отображения списка специалистов в интерфейсе QR-регистрации
    """
    try:
        # Импортируем локально для избежания circular dependency
        from sqlalchemy.orm import joinedload

        from app.models.clinic import Doctor

        # Получаем всех активных врачей с eager loading user relationship
        doctors = (
            db.query(Doctor)
            .filter(Doctor.active == True)
            .options(joinedload(Doctor.user))
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Маппинг специальностей на русские названия и иконки
        specialty_mapping = {
            'cardiology': {'name': 'Кардиолог', 'icon': '❤️', 'color': '#FF3B30'},
            'cardio': {'name': 'Кардиолог', 'icon': '❤️', 'color': '#FF3B30'},
            'dermatology': {
                'name': 'Дерматолог-косметолог',
                'icon': '✨',
                'color': '#FF9500',
            },
            'derma': {
                'name': 'Дерматолог-косметолог',
                'icon': '✨',
                'color': '#FF9500',
            },
            'dentistry': {'name': 'Стоматолог', 'icon': '🦷', 'color': '#007AFF'},
            'dentist': {'name': 'Стоматолог', 'icon': '🦷', 'color': '#007AFF'},
            'laboratory': {'name': 'Лаборатория', 'icon': '🔬', 'color': '#34C759'},
            'lab': {'name': 'Лаборатория', 'icon': '🔬', 'color': '#34C759'},
        }

        specialists_list = []
        for doctor in doctors:
            specialty_key = doctor.specialty.lower() if doctor.specialty else None
            if not specialty_key:
                continue

            # Нормализуем ключ специальности
            normalized_specialty = None
            for key in specialty_mapping.keys():
                if key in specialty_key or specialty_key in key:
                    normalized_specialty = key
                    break

            if not normalized_specialty:
                # Если специальность не найдена в маппинге, используем оригинальную
                normalized_specialty = specialty_key
                specialty_mapping[normalized_specialty] = {
                    'name': doctor.specialty or 'Специалист',
                    'icon': '👨‍⚕️',
                    'color': '#8E8E93',
                }

            specialists_list.append({
                'id': doctor.id,
                'specialty': normalized_specialty,
                'specialty_display': specialty_mapping[normalized_specialty]['name'],
                'icon': specialty_mapping[normalized_specialty]['icon'],
                'color': specialty_mapping[normalized_specialty]['color'],
                'doctor_name': doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
                'cabinet': doctor.cabinet,
            })

        # Сортируем по порядку: кардиолог, дерматолог, стоматолог, лаборатория
        sort_order = [
            'cardiology',
            'cardio',
            'dermatology',
            'derma',
            'dentistry',
            'dentist',
            'laboratory',
            'lab',
        ]
        specialists_list.sort(
            key=lambda x: (
                sort_order.index(x['specialty'])
                if x['specialty'] in sort_order
                else 999,
                x['doctor_name'] or '',
                x['id'],
            )
        )

        return {
            'success': True,
            'specialists': specialists_list,
            'total': len(specialists_list),
        }

    except Exception as e:

        logger.error(
            "[get_available_specialists] ОШИБКА: %s: %s",
            type(e).__name__,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


