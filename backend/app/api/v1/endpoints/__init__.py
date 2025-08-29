from __future__ import annotations

# Перечень модулей с роутерами (для явной регистрации в v1/api.py при желании).
ENDPOINT_MODULES = [
    "health",
    "patients",
    "auth",
    "queues",
    "visits",
    "lab",
    "payments",
    "settings",
    "print",
    "audit",
    "services",
    "schedule",
    "appointments",
    "online_queue",
    "users",
    "queue",
    "board",
    "reports",
    "payment_webhook",
]

__all__ = ["ENDPOINT_MODULES"]