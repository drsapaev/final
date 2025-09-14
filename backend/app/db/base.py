from __future__ import annotations

from app.db.base_class import Base  # noqa: F401

"""
Импортирует Base и подгружает все модули моделей, чтобы таблицы попали в metadata.
Alembic (env.py) импортирует Base отсюда.
"""

# Подгружаем модули моделей (имена классов не нужны — важен факт импорта).
# Если добавите новые модели — допишите импорт ниже.
from app.models import (  # noqa: F401, E402
    activation as _m_activation,
    appointment as _m_appointment,
    audit as _m_audit,
    clinic as _m_clinic,
    online_queue as _m_online_queue,
    emr as _m_emr,
    enums as _m_enums,
    lab as _m_lab,
    notification as _m_notification,
    online as _m_online,
    patient as _m_patient,
    payment as _m_payment,
    payment_webhook as _m_payment_webhook,
    # queue as _m_queue,  # Временно отключено
    schedule as _m_schedule,
    service as _m_service,
    setting as _m_setting,
    user as _m_user,
    visit as _m_visit,
)
