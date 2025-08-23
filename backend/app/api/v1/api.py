import importlib
import logging
from fastapi import APIRouter

log = logging.getLogger("api.include")

api_router = APIRouter()


def _safe_include(module_path: str, prefix: str = "", tags: list[str] | None = None):
    try:
        mod = importlib.import_module(module_path)
        router = getattr(mod, "router")
        api_router.include_router(router, prefix=prefix, tags=tags)
        log.info("Mounted %s at %s", module_path, prefix or "/")
    except Exception as e:
        log.error("Failed to import %s: %s", module_path, e)


# ---- AUTH
_safe_include("app.api.v1.endpoints.auth", prefix="/auth", tags=["auth"])

# ---- CRUD
_safe_include("app.api.v1.endpoints.patients", prefix="/patients", tags=["patients"])
_safe_include("app.api.v1.endpoints.visits", prefix="/visits", tags=["visits"])
_safe_include("app.api.v1.endpoints.services", prefix="/services", tags=["services"])
_safe_include("app.api.v1.endpoints.payments", prefix="/payments", tags=["payments"])
_safe_include("app.api.v1.endpoints.settings", prefix="/settings", tags=["settings"])
_safe_include("app.api.v1.endpoints.audit", prefix="/audit", tags=["audit"])

# ---- QUEUE core
_safe_include("app.api.v1.endpoints.queues", prefix="/queues", tags=["queues"])

# ---- APPOINTMENTS: внутри файла уже prefix="/appointments", поэтому без доп. префикса
_safe_include("app.api.v1.endpoints.appointments", prefix="", tags=["appointments"])

# ---- ONLINE-QUEUE алиасы (prefix задан внутри файла как "/online-queue")
_safe_include("app.api.v1.endpoints.online_queue", prefix="", tags=["online-queue"])
