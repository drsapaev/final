from __future__ import annotations

from app.db.base_class import Base  # noqa: F401
from app.models import *  # noqa: F401,F403

"""
Импортирует Base и подгружает все модули моделей, чтобы таблицы попали в metadata.
Alembic (env.py) импортирует Base отсюда.
"""

# Подгружаем модули моделей (имена классов не нужны — важен факт импорта).
# Если добавите новые модели — допишите импорт ниже.


# Derma history read model (#3520/#3521): the after_flush projection
# listener must be installed wherever ORM sessions exist (app runtime,
# tests, tools). Registering here — the module every entry point imports
# (routers via deps, conftest, alembic env) — keeps the read model
# maintained regardless of which surface writes the sources.
from app.services.derma_history_projection import (  # noqa: E402
    install_derma_history_listener,
)

install_derma_history_listener()
