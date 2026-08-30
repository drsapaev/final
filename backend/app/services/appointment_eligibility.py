"""Doctor eligibility contract for appointment WRITE paths.

Single source of truth shared by every live appointment writer:

- web   POST/PUT /appointments            (app/api/v1/endpoints/appointments.py)
- mobile POST /mobile/appointments/book   (app/api/v1/endpoints/mobile_api.py)
- telegram Mini App booking               (app/api/v1/endpoints/telegram_webhook/_routes.py)

A new/changed booking must target a clinically eligible doctor, mirroring the
same contract enforced elsewhere (lifecycle PR, round-1 Codex P1-D and its
round-2 follow-up):

- the registrar doctor selector hides inactive/incomplete doctors;
- the QR/online queue join and the public /queue/available-specialists
  listing exclude them;
- user deactivation/demotion deactivates the linked Doctor profile.

Without this guard a writer could still book a DEACTIVATED (ghost-mirrored)
or INCOMPLETE (auto-created specialty="general" placeholder) doctor by raw
doctor_id, bypassing the whole eligibility contract.

Only NEW/CHANGED bookings are validated: editing an existing appointment
without reassigning the doctor stays legal (historical rows may reference
doctors that were deactivated later). doctor_id=None (doctorless
appointment) has no doctor to validate.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.services.user_mgmt._base import is_doctor_profile_incomplete


def ensure_doctor_eligible_for_appointment(
    db: Session, doctor_id: int | None
) -> None:
    """Raise unless ``doctor_id`` resolves to an eligible doctor.

    Eligible = exists (404), active (409), completed profile (409).
    ``doctor_id=None`` short-circuits (nothing to validate).
    """
    if doctor_id is None:
        return
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Врач не найден",
        )
    if not doctor.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Врач деактивирован и недоступен для записи. Выберите "
                "другого врача или восстановите профиль врача."
            ),
        )
    if is_doctor_profile_incomplete(doctor.specialty):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Профиль врача не завершён (специализация не указана) и "
                "недоступен для записи. Администратор должен указать "
                "специализацию профиля."
            ),
        )
