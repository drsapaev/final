"""CSRF protection middleware (double-submit cookie pattern).

Validates ``X-CSRF-Token`` header against ``csrf_token`` cookie for
state-changing requests (POST / PUT / PATCH / DELETE).

Context:
- The ``/auth/csrf-token`` endpoint (``app/api/v1/endpoints/auth.py``)
  issues a random ``secrets.token_urlsafe(32)`` token and stores it in
  the ``csrf_token`` cookie (``httponly=False``, ``samesite=lax``) so
  the frontend can read it via ``document.cookie`` and replay it in
  the ``X-CSRF-Token`` header on mutating requests.
- The frontend axios client (``frontend/src/api/client.ts``) already
  fetches ``/auth/csrf-token`` (single-flight) and attaches the
  ``X-CSRF-Token`` header to all POST/PUT/PATCH/DELETE requests.
- Until this middleware was added, the token was issued but never
  validated — the ``CSRF_ENABLED`` flag in ``main.py`` referenced a
  module that did not exist (audit C-1).

Design choices:
- **Double-submit cookie** (not signed token): simpler, no server-side
  state, no DB lookup per request. The cookie is ``SameSite=Lax``,
  which already blocks most cross-site POSTs in modern browsers; this
  middleware is the second factor for the cases SameSite does not
  cover (e.g. older browsers, navigational GETs that mutate state via
  a hidden form, subdomain attacks).
- **Constant-time comparison** via ``hmac.compare_digest`` to avoid
  timing oracles on token equality.
- **GET / HEAD / OPTIONS / WebSocket upgrade requests are exempt** —
  they must be safe and idempotent per HTTP semantics; CSRF protection
  is only meaningful for state-changing verbs.
- **Whitelisted paths**: ``/auth/login``, ``/auth/json-login``,
  ``/auth/csrf-token``, ``/auth/refresh``, ``/health``, ``/healthz``,
  ``/api/v1/health`` and all payment-provider webhook endpoints
  (``/payments/webhook/*``). These endpoints either establish the
  session (login/refresh), issue the CSRF token itself, are
  unauthenticated health probes, or are machine-to-machine callbacks
  from PayMe/Click/Kaspi that authenticate via HMAC signatures, not
  cookies.
- **Failure mode: 403 + JSON body** with a clear ``reason`` field so
  the frontend can detect CSRF drift and re-fetch ``/auth/csrf-token``.
- **Safe methods without cookie**: if a request has no ``csrf_token``
  cookie at all (e.g. a fresh browser session before any
  ``/auth/csrf-token`` call), the middleware still rejects
  state-changing requests — the frontend MUST bootstrap the cookie
  first. This is by design: the cookie is set on the first
  ``/auth/csrf-token`` GET, which the frontend already issues at app
  startup.

Integration notes:
- Registered in ``app/main.py`` only when ``CSRF_ENABLED=1`` (default
  in production). Set ``CSRF_ENABLED=0`` to disable (e.g. for local
  dev where the frontend runs on a different origin and you do not
  want to configure CORS for the cookie).
- ``enabled`` constructor parameter is kept for backward compatibility
  with the ``app.add_middleware(CSRFMiddleware, enabled=True)`` call
  site in ``main.py``; when ``False`` the middleware is a no-op pass
  through.
"""
from __future__ import annotations

import hmac
import logging
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# HTTP methods that MUST NOT mutate server state and are therefore
# exempt from CSRF validation. Per RFC 7231 §4.2.1.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# Paths exempt from CSRF validation even for state-changing methods.
# Each entry is matched as a prefix against request.url.path.
#
# Rationale per path:
# - /auth/login, /auth/json-login: establishing the session; the CSRF
#   token is issued *after* login by /auth/csrf-token.
# - /auth/refresh: uses refresh_token (not cookie-based auth).
# - /auth/csrf-token: the endpoint that issues the token itself.
# - /auth/webauthn/*: passkey registration/login uses challenge
#   tokens, not cookie auth.
# - /health, /healthz, /api/v1/health: unauthenticated probes.
# - /payments/webhook/*: PayMe/Click/Kaspi callbacks authenticate via
#   HMAC signatures in Authorization header or body, not cookies.
# - /telegram/webhook, /telegram/webhook/enhanced, /telegram/bot/webhook:
#   Telegram Bot API callbacks authenticate via
#   X-Telegram-Bot-Api-Secret-Token header (constant-time comparison in
#   _validate_webhook_secret). Server-to-server, not browser.
#   P1-3 (post-merge stabilization): these are EXACT-match only — NOT
#   prefix-match. This prevents accidental over-exemption of sibling
#   admin endpoints like /telegram/webhook/test (which is browser-facing
#   and requires CSRF protection).
# - /emergency: break-glass token-based access, not cookie auth.
#
# P1-3: paths that are exempted by PREFIX (e.g. /payments/webhook/ is a
# prefix for /payments/webhook/click, /payments/webhook/payme, etc.).
CSRF_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/auth/login",
    "/auth/json-login",
    "/auth/refresh",
    "/auth/csrf-token",
    "/auth/webauthn",
    "/health",
    "/healthz",
    "/api/v1/health",
    "/api/v1/payments/webhook/",
    "/emergency",
    "/api/v1/emergency",
)

# P1-3: paths that are exempted by EXACT match only (no prefix matching).
# These are webhook endpoints that share a path prefix with browser-facing
# admin endpoints. Using exact match prevents the admin endpoints from
# accidentally losing CSRF protection.
#
# Example: /api/v1/telegram/webhook is a webhook (exempted), but
# /api/v1/telegram/webhook/test is an admin endpoint (NOT exempted).
# If we used prefix match, /webhook/test would be incorrectly exempted.
CSRF_EXEMPT_EXACT: frozenset[str] = frozenset({
    "/api/v1/telegram/webhook",
    "/api/v1/telegram/webhook/enhanced",
    "/api/v1/telegram/bot/webhook",
})

# Backward compatibility: combined set for any code that still references
# CSRF_EXEMPT_PATHS. New code should use CSRF_EXEMPT_PREFIXES or
# CSRF_EXEMPT_EXACT directly.
CSRF_EXEMPT_PATHS: tuple[str, ...] = CSRF_EXEMPT_PREFIXES

# Cookie name — must match /auth/csrf-token endpoint (auth.py:149).
CSRF_COOKIE_NAME = "csrf_token"

# Header name — must match frontend axios interceptor
# (frontend/src/api/client.ts) and CORS allow_headers in main.py:325.
CSRF_HEADER_NAME = "X-CSRF-Token"


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validate ``X-CSRF-Token`` header against ``csrf_token`` cookie.

    Double-submit cookie pattern: the token is stored in a cookie
    (auto-sent by the browser) AND echoed in a custom header (which
    cross-site JavaScript cannot set without explicit CORS allowance).
    A request is accepted only if both are present and equal.

    See module docstring for design rationale and exempt paths.
    """

    def __init__(
        self,
        app,  # noqa: ANN001 — Starlette passes the ASGI app
        enabled: bool = True,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        if not enabled:
            logger.warning(
                "CSRFMiddleware registered with enabled=False — "
                "all state-changing requests will bypass CSRF validation"
            )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Fast path: middleware disabled or safe method.
        if not self.enabled or request.method.upper() in SAFE_METHODS:
            return await call_next(request)

        path = request.url.path

        # Exempt paths (login, csrf-token issue, webhooks, health).
        # P1-3: prefix-based exemption for paths that are genuinely
        # hierarchical (e.g. /payments/webhook/click).
        for exempt in CSRF_EXEMPT_PREFIXES:
            if path == exempt or path.startswith(exempt):
                return await call_next(request)

        # P1-3: exact-match exemption for webhook endpoints that share
        # a path prefix with browser-facing admin endpoints. Using exact
        # match prevents the admin endpoints from accidentally losing
        # CSRF protection (e.g. /telegram/webhook/test must NOT be
        # exempted just because /telegram/webhook is).
        if path in CSRF_EXEMPT_EXACT:
            return await call_next(request)

        # WebSocket upgrade requests — CSRF does not apply; the WS
        # handler validates the JWT via Sec-WebSocket-Protocol
        # subprotocol (bearer.<token>).
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        # Reject if either token is missing or they do not match.
        # Constant-time comparison via hmac.compare_digest prevents
        # timing oracles on token equality.
        #
        # Compute the rejection reason ONCE and use it in both the
        # log line and the response body — keeps them in sync.
        if not cookie_token:
            rejection_reason = "missing_cookie"
        elif not header_token:
            rejection_reason = "missing_header"
        elif not hmac.compare_digest(str(cookie_token), str(header_token)):
            rejection_reason = "mismatch"
        else:
            rejection_reason = None  # all checks passed

        if rejection_reason is not None:
            logger.info(
                "csrf.rejected method=%s path=%s reason=%s",
                request.method,
                path,
                rejection_reason,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "CSRF validation failed",
                    "reason": rejection_reason,
                    # Hint for the frontend: re-fetch /auth/csrf-token
                    # to refresh the cookie, then retry.
                    "recovery": "GET /auth/csrf-token",
                },
                headers={"X-CSRF-Status": "rejected"},
            )

        return await call_next(request)
