"""Split from qr_queue.py."""

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

        # Получаем всех активных врачей с eager loading user relationship.
        # Incomplete ("general" sentinel) profiles are excluded as well:
        # this is a PATIENT-facing selector for QR self-registration — the
        # same lifecycle eligibility contract as the queue join itself
        # (Codex round-2 P2: a promoted Doctor with the placeholder
        # specialty must not appear selectable and then dead-end on join).
        # Pagination is applied after QueueProfile eligibility, which is
        # resolved below.
        from app.services.user_mgmt._base import INCOMPLETE_DOCTOR_SPECIALTY

        doctors = (
            db.query(Doctor)
            .filter(
                Doctor.active == True,  # noqa: E712
                Doctor.specialty != INCOMPLETE_DOCTOR_SPECIALTY,
            )
            .options(joinedload(Doctor.user))
            .all()
        )

        # PR-28: Build specialty_mapping dynamically from QueueProfiles
        # (was hardcoded — new specialties like 'neurology' got default icon/name)
        from app.models.queue_profile import QueueProfile

        profiles = (
            db.query(QueueProfile)
            .filter(
                QueueProfile.is_active == True,
                QueueProfile.show_on_qr_page == True,
            )
            .all()
        )
        from app.services.queue_profile_availability import (
            load_queue_profile_availability,
            queue_profile_is_qr_selectable,
        )

        availability_by_profile = load_queue_profile_availability(db, profiles)
        profiles = [
            profile
            for profile in profiles
            if queue_profile_is_qr_selectable(profile, availability_by_profile[profile])
        ]

        # Build mapping from profile keys + queue_tags
        specialty_mapping = {}
        for profile in profiles:
            display_name = profile.title_ru or profile.title or profile.key
            icon = profile.icon or "👨‍⚕️"
            color = profile.color or "#8E8E93"
            # Map profile.key
            specialty_mapping[profile.key] = {
                "name": display_name,
                "icon": icon,
                "color": color,
            }
            # Map each queue_tag too
            for tag in profile.queue_tags or []:
                if tag not in specialty_mapping:
                    specialty_mapping[tag] = {
                        "name": display_name,
                        "icon": icon,
                        "color": color,
                    }

        specialists_list = []
        for doctor in doctors:
            specialty_key = doctor.specialty.lower() if doctor.specialty else None
            if not specialty_key:
                continue

            # PR-28: look up in dynamic mapping, fallback to raw specialty
            if specialty_key in specialty_mapping:
                normalized_specialty = specialty_key
            else:
                # Try partial match (e.g. 'cardiology' in 'cardiology_common')
                normalized_specialty = None
                for key in specialty_mapping.keys():
                    if key in specialty_key or specialty_key in key:
                        normalized_specialty = key
                        break

            if not normalized_specialty:
                # A QR selector must not advertise a doctor whose current
                # profile/parent policy would reject the subsequent join.
                continue

            specialists_list.append(
                {
                    "id": doctor.id,
                    "specialty": normalized_specialty,
                    "specialty_display": specialty_mapping[normalized_specialty][
                        "name"
                    ],
                    "icon": specialty_mapping[normalized_specialty]["icon"],
                    "color": specialty_mapping[normalized_specialty]["color"],
                    "doctor_name": (
                        doctor.user.full_name if doctor.user else f"Врач #{doctor.id}"
                    ),
                    "cabinet": doctor.cabinet,
                }
            )

        # Сортируем по порядку: кардиолог, дерматолог, стоматолог, лаборатория
        sort_order = [
            "cardiology",
            "cardio",
            "dermatology",
            "derma",
            "dentistry",
            "dentist",
            "laboratory",
            "lab",
        ]
        specialists_list.sort(
            key=lambda x: (
                (
                    sort_order.index(x["specialty"])
                    if x["specialty"] in sort_order
                    else 999
                ),
                x["doctor_name"] or "",
                x["id"],
            )
        )

        total = len(specialists_list)
        specialists_list = specialists_list[offset : offset + limit]

        return {
            "success": True,
            "specialists": specialists_list,
            "total": total,
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
