from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("clinic.main")

API_V1_STR = os.getenv("API_V1_STR", "/api/v1")
CORS_DISABLE = os.getenv("CORS_DISABLE", "0") == "1"
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "0") == "1"
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]

app = FastAPI(
    title="Clinic Manager API",
    version=os.getenv("APP_VERSION", "0.9.0"),
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

from app.ws.queue_ws import router as queue_ws_router, ws_queue  # noqa: E402

app.include_router(queue_ws_router)
app.add_api_websocket_route("/ws/dev-queue", ws_queue)

if not CORS_DISABLE:
    cfg = dict(allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    if CORS_ALLOW_ALL:
        app.add_middleware(CORSMiddleware, allow_origins=["*"], **cfg)
    else:
        app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, **cfg)

try:  # noqa: E402
    from app.api.deps import create_access_token  # type: ignore
except Exception as e:  # pragma: no cover
    log.error("dev-fallback: cannot import create_access_token (%s) -> using dummy token", e)


def create_access_token(sub: str) -> str:  # type: ignore
    return f"dev.{sub}"


try:
    from app.api.deps import get_current_user  # type: ignore # noqa: E402
    _HAS_CURRENT_USER = True
except Exception:
    _HAS_CURRENT_USER = False


@app.post(f"{API_V1_STR}/auth/login", tags=["auth"], summary="Login (fallback)")
async def _fallback_login(form: OAuth2PasswordRequestForm = Depends()):
    token = create_access_token(form.username)
    return {"access_token": token, "token_type": "bearer"}


@app.get(f"{API_V1_STR}/auth/me", tags=["auth"], summary="Me (fallback)")
async def _fallback_me():
    if _HAS_CURRENT_USER:
        try:
            # attempt to call the real dependency if available
            user: Dict[str, Any] = await get_current_user()  # type: ignore
        except Exception:
            user = {}
        return {
            "id": user.get("id"),
            "username": user.get("username"),
            "full_name": user.get("full_name"),
            "email": user.get("email"),
            "role": user.get("role"),
            "is_active": user.get("is_active", True),
        }
    return {"username": "dev", "role": "Admin", "is_active": True}


try:
    from app.api.v1.api import api_router as v1_router  # noqa: E402
    app.include_router(v1_router, prefix=API_V1_STR)
    log.info("Included api.v1.api router at %s", API_V1_STR)
except Exception as e:
    log.warning("WARN: failed to include api.v1.api (%s). Continuing.", e)


try:
    from app.api.v1.endpoints import auth as auth_ep  # noqa: E402
    app.include_router(auth_ep.router, prefix=f"{API_V1_STR}/auth", tags=["auth"])
    app.include_router(auth_ep.router, prefix="/auth", tags=["auth"])
    log.info("Included AUTH router at %s/auth and /auth", API_V1_STR)
except Exception as e:
    log.warning("WARN: failed to include AUTH router (%s).", e)


@app.get("/")
def root():
    return {
        "status": "ok",
        "name": "Clinic Queue Manager",
        "version": os.getenv("APP_VERSION", "0.9.0"),
        "api_v1": API_V1_STR,
        "env": os.getenv("APP_ENV", "dev"),
        "docs": "/docs",
        "openapi": "/openapi.json",
        "cors_disabled": CORS_DISABLE,
        "cors_allow_all": CORS_ALLOW_ALL,
        "origins": CORS_ORIGINS,
    }


@app.on_event("startup")
async def _print_routes() -> None:
    lines: List[str] = []
    for r in app.router.routes:
        path = getattr(r, "path", "")
        methods = ",".join(sorted(getattr(r, "methods", []) or []))
        name = getattr(r, "name", "")
        lines.append(f"{methods:20s} {path:40s} {name}")
    log.info("Mounted routes:\n%s", "\n".join(lines))
    log.info("Flags: WS_DEV_ALLOW=%s CORS_DISABLE=%s", os.getenv("WS_DEV_ALLOW"), os.getenv("CORS_DISABLE"))


@app.get("/_routes")
def _routes():
    items = []
    for r in app.router.routes:
        items.append(
            {
                "type": type(r).__name__,
                "path": getattr(r, "path", ""),
                "methods": list(getattr(r, "methods", []) or []),
                "name": getattr(r, "name", ""),
            }
        )
    return items