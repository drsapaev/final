from __future__ import annotations

"""
Импортирует Base и подгружает все модули моделей, чтобы таблицы попали в metadata.
Alembic (env.py) импортирует Base отсюда.
"""

from app.db.base_class import Base  # noqa: F401

# Подгружаем модули моделей (имена классов не нужны — важен факт импорта).
# Если добавите новые модели — допишите импорт ниже.
from app.models import (  # noqa: F401
    appointment as _m_appointment,
    audit as _m_audit,
    emr as _m_emr,
    enums as _m_enums,
    lab as _m_lab,
    online as _m_online,
    patient as _m_patient,
    payment as _m_payment,
    queue as _m_queue,
    schedule as _m_schedule,
    service as _m_service,
    setting as _m_setting,
    user as _m_user,
    visit as _m_visit,
)
