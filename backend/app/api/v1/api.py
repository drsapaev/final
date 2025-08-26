# app/api/v1/api.py
from __future__ import annotations

from fastapi import APIRouter

# важно: подключаем именно router из каждого модуля
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
    online_queue,  # <-- наш алиас онлайн-очереди
)

api_router = APIRouter()

# Auth
api_router.include_router(auth.router)  # дает /api/v1/auth/...

# Основные сущности
api_router.include_router(patients.router, prefix="/api/v1", tags=["auth"])     # /api/v1/patients/...
api_router.include_router(visits.router)       # /api/v1/visits/...
api_router.include_router(services.router)     # /api/v1/services/...
api_router.include_router(payments.router)     # /api/v1/payments/...
api_router.include_router(settings_ep.router)  # /api/v1/settings/...
api_router.include_router(audit.router)        # /api/v1/audit/...

# Очередь / запись
api_router.include_router(queues.router)        # /api/v1/queues/...
api_router.include_router(appointments.router)  # /api/v1/appointments/...
api_router.include_router(online_queue.router)  # /api/v1/online-queue/...
