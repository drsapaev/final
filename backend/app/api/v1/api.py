# app/api/v1/api.py
from __future__ import annotations

from fastapi import APIRouter

# подключаем router из каждого модуля
from app.api.v1.endpoints import activation as activation_ep
from app.api.v1.endpoints import (admin_providers, admin_users, analytics,
                                  appointment_flow, appointments, audit, auth)
from app.api.v1.endpoints import board as board_ep
from app.api.v1.endpoints import cardio, dental, derma
from app.api.v1.endpoints import health as health_ep
from app.api.v1.endpoints import (lab_specialized, online_queue, patients,
                                  payment_webhook, payments)
from app.api.v1.endpoints import print as print_ep
from app.api.v1.endpoints import queue, queues
from app.api.v1.endpoints import reports as reports_ep
from app.api.v1.endpoints import schedule, services
from app.api.v1.endpoints import settings as settings_ep
from app.api.v1.endpoints import visits

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
api_router.include_router(
    appointment_flow.router, prefix="/appointments", tags=["appointment_flow"]
)
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(health_ep.router, tags=["health"])
api_router.include_router(activation_ep.router, tags=["activation"])
