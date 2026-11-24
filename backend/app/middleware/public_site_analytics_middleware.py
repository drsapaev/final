"""Bound collector input before generic middleware and SDK request extraction."""

from starlette.datastructures import Headers
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.pii_masker import (
    PUBLIC_SITE_ANALYTICS_MAX_TOKEN_BYTES,
    is_public_site_analytics_ingest_path,
)


class PublicSiteAnalyticsIntakeMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and is_public_site_analytics_ingest_path(scope["path"])
        ):
            status_code = self._rejection_status(Headers(scope=scope))
            if status_code is not None:
                response = Response(
                    status_code=status_code, headers={"Cache-Control": "no-store"}
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)

    @staticmethod
    def _rejection_status(headers: Headers) -> int | None:
        if "idempotency-key" in headers:
            return 400

        lengths = headers.getlist("content-length")
        if lengths:
            length = lengths[0]
            if len(lengths) != 1 or not length.isascii() or not length.isdecimal():
                return 400

            length = length.lstrip("0") or "0"
            limit = PUBLIC_SITE_ANALYTICS_MAX_TOKEN_BYTES
            if len(length) > len(str(limit)) or int(length) > limit:
                return 413

        return None
