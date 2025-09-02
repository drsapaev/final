from __future__ import annotations

"""
Импортирует Base и подгружает все модули моделей, чтобы таблицы попали в metadata.
Alembic (env.py) импортирует Base отсюда.
"""

from app.db.base_class import Base  # noqa: F401

# Подгружаем модули моделей (имена классов не нужны — важен факт импорта).
# Если добавите новые модели — допишите импорт ниже.
from app.models import user as _m_user         # noqa: F401
from app.models import patient as _m_patient   # noqa: F401
from app.models import queue as _m_queue       # noqa: F401
from app.models import visit as _m_visit       # noqa: F401
from app.models import lab as _m_lab           # noqa: F401
from app.models import payment as _m_payment   # noqa: F401
from app.models import setting as _m_setting   # noqa: F401
from app.models import audit as _m_audit       # noqa: F401
from app.models import service as _m_service   # noqa: F401
from app.models import schedule as _m_schedule # noqa: F401
from app.models import online as _m_online     # noqa: F401
from app.models import appointment as _m_appointment # noqa: F401
from app.models import emr as _m_emr           # noqa: F401
from app.models import enums as _m_enums       # noqa: F401