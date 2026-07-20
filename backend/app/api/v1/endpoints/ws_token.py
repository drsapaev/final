"""Shared WebSocket auth token extraction (PR-4).

Audit (PR-4) found that 5 WS endpoints accept JWT in URL query param
(?token=...). URLs (and query strings) get logged by proxies/CDNs and
leak in Referer headers — that exposes JWTs.

This module provides a single ``extract_ws_token`` helper that prefers
the secure sources (Sec-WebSocket-Protocol subprotocol ``bearer.<token>``
or ``Authorization`` header) and falls back to the legacy ``?token=...``
query param with a deprecation warning, so existing clients keep working
while new clients can adopt the secure path.

Usage::

    from app.api.v1.endpoints.ws_token import extract_ws_token

    @router.websocket("/ws/foo")
    async def ws_foo(websocket: WebSocket):
        token = extract_ws_token(websocket)
        if not token:
            await websocket.close(code=4401)
            return
        user = await authenticate_websocket_token(token, db)
        ...
"""
from __future__ import annotations

import logging
from typing import Final

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Subprotocol prefix used to convey a JWT without it appearing in the URL.
# Clients pass it as the ``Sec-WebSocket-Protocol`` header value:
#   Sec-WebSocket-Protocol: bearer.<jwt>
# FastAPI surfaces this as ``websocket.headers["sec-websocket-protocol"]``.
SUBPROTOCOL_PREFIX: Final[str] = "bearer."

# Header names we accept for JWT. ``Authorization: Bearer <jwt>`` is the
# canonical HTTP header; some WS clients cannot set Authorization, so we
# also accept the explicit ``X-WS-Token`` header as a non-URL alternative.
_AUTH_HEADER_NAMES: Final[tuple[str, ...]] = (
    "authorization",
    "Authorization",
    "x-ws-token",
    "X-WS-Token",
)


def _extract_from_subprotocol(websocket: WebSocket) -> str | None:
    """Pull a JWT out of the ``Sec-WebSocket-Protocol`` subprotocol value.

    Browsers can't set arbitrary headers on WebSocket handshakes, but they
    CAN set the subprotocol. The convention ``bearer.<jwt>`` is widely
    used (e.g. by @fastify/websocket, Phoenix, Action Cable).
    """
    raw = websocket.headers.get("sec-websocket-protocol")
    if not raw:
        return None
    # Browsers send a comma-separated list; pick the first bearer.* entry.
    for proto in raw.split(","):
        proto = proto.strip()
        if proto.startswith(SUBPROTOCOL_PREFIX):
            token = proto[len(SUBPROTOCOL_PREFIX):].strip()
            if token:
                return token
    return None


def _extract_from_auth_header(websocket: WebSocket) -> str | None:
    """Pull a JWT out of ``Authorization: Bearer <jwt>`` or ``X-WS-Token``."""
    for name in _AUTH_HEADER_NAMES:
        value = websocket.headers.get(name)
        if not value:
            continue
        value = value.strip()
        if value.lower().startswith("bearer "):
            token = value[7:].strip()
            if token:
                return token
        # X-WS-Token: raw JWT, no Bearer prefix
        if name.lower() == "x-ws-token" and value:
            return value
    return None


def _extract_from_query(websocket: WebSocket) -> str | None:
    """Legacy: pull ?token=... from the query string (DEPRECATED)."""
    return websocket.query_params.get("token")


def extract_ws_token(websocket: WebSocket) -> str | None:
    """Resolve a JWT for a WebSocket handshake, preferring secure sources.

    Resolution order (most-secure first):
      1. ``Sec-WebSocket-Protocol: bearer.<jwt>`` subprotocol
      2. ``Authorization: Bearer <jwt>`` (or ``X-WS-Token``) header
      3. ``?token=<jwt>`` query string — emits a deprecation warning

    Returns the raw JWT string, or None if no token was found.
    """
    token = _extract_from_subprotocol(websocket)
    if token:
        return token

    token = _extract_from_auth_header(websocket)
    if token:
        return token

    token = _extract_from_query(websocket)
    if token:
        # PR-4: query-string JWT is insecure — it leaks in proxy logs,
        # CDN logs, browser history, and Referer headers. Keep accepting
        # it for backward compatibility, but warn loudly so monitoring
        # picks up clients that still use it.
        logger.warning(
            "WebSocket auth via ?token= query param is deprecated and insecure; "
            "use Sec-WebSocket-Protocol subprotocol 'bearer.<token>' or "
            "Authorization header instead. path=%s",
            getattr(getattr(websocket, "url", None), "path", "<unknown>"),
        )
        return token

    return None
