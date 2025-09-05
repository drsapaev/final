# app/api/v1/api.py
from __future__ import annotations

from fastapi import APIRouter

# подключаем router из каждого модуля
from app.api.v1.endpoints import (
    activation as activation_ep,
    admin_ai,
    admin_clinic,
    admin_doctors,
    admin_providers,
    admin_stats,
    admin_telegram,
    admin_users,
    analytics,
    api_documentation,
    appointment_flow,
    appointments,
    auth,
    board as board_ep,
    cardio,
    dental,
    derma,
    docs,
    health as health_ep,
    lab_specialized,
    notifications,
    online_queue,
    patients,
    payment_webhook,
    payments,
    print as print_ep,
    queue,
    queues,
    reports as reports_ep,
    schedule,
    services,
    specialized_panels,
    visits,
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
api_router.include_router(admin_ai.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_clinic.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_doctors.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_providers.router, tags=["admin"])
api_router.include_router(admin_telegram.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_stats.router, tags=["admin"])
api_router.include_router(admin_users.router)
api_router.include_router(schedule.router, tags=["schedule"])
api_router.include_router(queue.router, prefix="/queue", tags=["queue"])
api_router.include_router(cardio.router, tags=["cardio"])
api_router.include_router(derma.router, tags=["derma"])
api_router.include_router(dental.router, tags=["dental"])
api_router.include_router(lab_specialized.router, tags=["lab_specialized"])
api_router.include_router(
    appointment_flow.router, prefix="/appointments", tags=["appointment_flow"]
)
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(
    notifications.router, prefix="/notifications", tags=["notifications"]
)
api_router.include_router(docs.router, prefix="/docs", tags=["documentation"])
api_router.include_router(
    api_documentation.router, prefix="/documentation", tags=["api-docs"]
)
api_router.include_router(
    specialized_panels.router, prefix="/specialized", tags=["specialized-panels"]
)
api_router.include_router(health_ep.router, tags=["health"])
api_router.include_router(activation_ep.router, tags=["activation"])
