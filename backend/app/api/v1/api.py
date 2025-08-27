# app/api/v1/api.py
from __future__ import annotations

from fastapi import APIRouter

# подключаем router из каждого модуля
from app.api.v1.endpoints import (
    auth,
    patients,
    visits,
    services,
    payments,
    settings as settings_ep,
    audit,
    appointments,
    queues,
    online_queue,
    health as health_ep,        # <-- добавлено
    activation as activation_ep # <-- добавлено
)

api_router = APIRouter()

# Auth (/login, /me и т.д.)
api_router.include_router(auth.router)

# Основные сущности (без лишних префиксов!)
api_router.include_router(patients.router)       # было prefix="/api/v1" -> убрано
api_router.include_router(visits.router)
api_router.include_router(services.router)
api_router.include_router(payments.router)
api_router.include_router(settings_ep.router)
api_router.include_router(audit.router)

# Очередь / запись
api_router.include_router(queues.router)
api_router.include_router(appointments.router)
api_router.include_router(online_queue.router)

# Health / Activation
api_router.include_router(health_ep.router)
api_router.include_router(activation_ep.router)
