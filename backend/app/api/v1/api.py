# --- BEGIN app/api/v1/api.py ---
from __future__ import annotations

import logging
from fastapi import APIRouter

log = logging.getLogger("api.include")

api_router = APIRouter()

def _safe_include(modpath: str, prefix: str, tag: str) -> None:
    """Подключает router из указанного модуля, логирует ошибку, если что-то пошло не так."""
    try:
        mod = __import__(modpath, fromlist=["router"])
        router = getattr(mod, "router", None)
        if router is None:
            raise RuntimeError(f"{modpath} has no 'router'")
        api_router.include_router(router, prefix=prefix, tags=[tag])
        log.info("Included router from %s", modpath)
    except Exception as e:  # noqa: BLE001
        log.error("Failed to include %s: %s", modpath, e)

# базовые
_safe_include("app.api.v1.endpoints.auth",          "/auth",           "auth")
_safe_include("app.api.v1.endpoints.patients",      "/patients",       "patients")
_safe_include("app.api.v1.endpoints.visits",        "/visits",         "visits")
_safe_include("app.api.v1.endpoints.services",      "/services",       "services")
_safe_include("app.api.v1.endpoints.payments",      "/payments",       "payments")
_safe_include("app.api.v1.endpoints.settings",      "/settings",       "settings")
_safe_include("app.api.v1.endpoints.audit",         "/audit",          "audit")
_safe_include("app.api.v1.endpoints.schedule",      "/appointments",   "appointments")

# очереди
_safe_include("app.api.v1.endpoints.queues",        "/queues",         "queues")
_safe_include("app.api.v1.endpoints.online_queue",  "/online-queue",   "online-queue")
# --- END app/api/v1/api.py ---
