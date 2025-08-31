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
    admin_providers,
    schedule,
    queue,
    cardio,
    derma,
    dental,
    lab_specialized,
    admin_users,
)

api_router = APIRouter()

# Auth (/login, /me и т.д.)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
api_router.include_router(visits.router, prefix="/visits", tags=["visits"])
api_router.include_router(services.router, prefix="/services", tags=["services"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(queues.router, prefix="/queues", tags=["queues"])
api_router.include_router(appointments.router, tags=["appointments"])
api_router.include_router(online_queue.router, tags=["online-queue"])
api_router.include_router(print_ep.router, tags=["print"])
api_router.include_router(board_ep.router, tags=["board"])
api_router.include_router(reports_ep.router, tags=["reports"])
api_router.include_router(payment_webhook.router, tags=["webhooks"])
api_router.include_router(admin_providers.router, tags=["admin"])
api_router.include_router(admin_users.router)
api_router.include_router(schedule.router, tags=["schedule"])
api_router.include_router(queue.router, prefix="/queue", tags=["queue"])
api_router.include_router(cardio.router, tags=["cardio"])
api_router.include_router(derma.router, tags=["derma"])
api_router.include_router(dental.router, tags=["dental"])
api_router.include_router(lab_specialized.router, tags=["lab_specialized"])
api_router.include_router(health_ep.router, tags=["health"])
api_router.include_router(activation_ep.router, tags=["activation"])
