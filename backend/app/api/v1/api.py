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
    print as print_ep,
    health as health_ep,
    activation as activation_ep,
    board as board_ep,
    reports as reports_ep,
    payment_webhook,
)

api_router = APIRouter()

# Auth (/login, /me и т.д.)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
api_router.include_router(visits.router, prefix="/visits", tags=["visits"])
api_router.include_router(services.router, prefix="/services", tags=["services"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(queues.router, prefix="/queue", tags=["queue"])
api_router.include_router(appointments.router, tags=["appointments"])
api_router.include_router(online_queue.router, tags=["online-queue"])
api_router.include_router(print_ep.router, tags=["print"])
api_router.include_router(board_ep.router, tags=["board"])
api_router.include_router(reports_ep.router, tags=["reports"])
api_router.include_router(payment_webhook.router, tags=["webhooks"])
api_router.include_router(health_ep.router, tags=["health"])
api_router.include_router(activation_ep.router, tags=["activation"])
