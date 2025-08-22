# kept + extended: центральный роутер API v1
from __future__ import annotations

import importlib
import logging
from typing import Optional, List
from fastapi import APIRouter

log = logging.getLogger("api.include")

# ВАЖНО: объявляем api_router СНАЧАЛА
api_router = APIRouter()


def _safe_include(
    module_path: str,
    *,
    attr: str = "router",
    prefix: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> None:
    """
    Импортирует модуль и, если в нём есть APIRouter по имени `attr`, подключает его.
    Ошибки импорта логируем (чтобы видеть причину, если роутер не подключился), но запуск не ломаем.
    """
    try:
        mod = importlib.import_module(module_path)
    except Exception as e:
        log.exception("Failed to import %s: %s", module_path, e)
        return
    router = getattr(mod, attr, None)
    if router is None:
        log.warning("Module %s has no attr %r", module_path, attr)
        return

    kw = {}
    if prefix:
        kw["prefix"] = prefix
    if tags:
        kw["tags"] = tags
    api_router.include_router(router, **kw)
    log.info("Included router from %s %s", module_path, kw or "")
    

# -------------------------
# Роутеры
# -------------------------
# /auth/*
_safe_include("app.api.v1.endpoints.auth", prefix="/auth", tags=["auth"])

# Остальные модули (подключаем, если есть)
_safe_include("app.api.v1.endpoints.patients")
_safe_include("app.api.v1.endpoints.visits")
_safe_include("app.api.v1.endpoints.services")
_safe_include("app.api.v1.endpoints.payments")
_safe_include("app.api.v1.endpoints.settings")
_safe_include("app.api.v1.endpoints.audit")
_safe_include("app.api.v1.endpoints.schedule")

# Очереди/запись
_safe_include("app.api.v1.endpoints.queues")
_safe_include("app.api.v1.endpoints.appointments")
_safe_include("app.api.v1.endpoints.online_queue")
