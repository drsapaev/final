"""Anonymous intake for public interactions and strict Admin reporting."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.pii_masker import PUBLIC_SITE_ANALYTICS_MAX_TOKEN_BYTES
from app.core.rate_limiter import RATE_LIMITS, limiter
from app.db.session import get_db
from app.models.public_site_analytics import PublicSiteAnalyticsEvent
from app.models.user import User
from app.repositories.public_site_analytics_repository import (
    PublicSiteAnalyticsRepository,
)
from app.schemas.public_site_analytics import (
    PublicSiteAnalyticsDayOut,
    PublicSiteAnalyticsReportOut,
)

logger = logging.getLogger(__name__)
router = APIRouter()
_NO_STORE = {"Cache-Control": "no-store"}
_EVENT_TOKENS = {
    event.value.encode("ascii"): event for event in PublicSiteAnalyticsEvent
}
_REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "text/plain": {
                "schema": {
                    "type": "string",
                    "enum": [event.value for event in PublicSiteAnalyticsEvent],
                    "maxLength": PUBLIC_SITE_ANALYTICS_MAX_TOKEN_BYTES,
                }
            }
        },
    }
}


def _record_event(db: Session, event: PublicSiteAnalyticsEvent) -> None:
    try:
        PublicSiteAnalyticsRepository(db).increment(
            event_code=event, observed_at=datetime.now(UTC)
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


@router.post(
    "/public-site/analytics/events",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    operation_id="record_public_site_analytics_event",
    openapi_extra=_REQUEST_BODY,
    responses={
        400: {"description": "Invalid event or unexpected request data."},
        403: {"description": "Missing or disallowed browser origin."},
        413: {"description": "Event token exceeds the fixed byte limit."},
        415: {"description": "Expected an unencoded text/plain event token."},
        429: {"description": "Too many requests."},
        503: {"description": "Collection is disabled or temporarily unavailable."},
    },
)
@limiter.limit(RATE_LIMITS["default"])
async def record_public_site_analytics_event(
    request: Request, db: Session = Depends(get_db)
) -> Response:
    if not settings.PUBLIC_SITE_ANALYTICS_ENABLED:
        return Response(status_code=503, headers=_NO_STORE)

    origins = request.headers.getlist("origin")
    if (
        len(origins) != 1
        or origins[0] in {"", "*", "null"}
        or origins[0] not in settings.BACKEND_CORS_ORIGINS
    ):
        return Response(status_code=403, headers=_NO_STORE)
    if request.scope.get("query_string") or any(
        name in request.headers
        for name in (
            "authorization",
            "proxy-authorization",
            "cookie",
            "referer",
            "sentry-trace",
            "baggage",
        )
    ):
        return Response(status_code=400, headers=_NO_STORE)

    content_type = (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    )
    if content_type != "text/plain" or "content-encoding" in request.headers:
        return Response(status_code=415, headers=_NO_STORE)

    payload = bytearray()
    try:
        async for chunk in request.stream():
            if len(payload) + len(chunk) > PUBLIC_SITE_ANALYTICS_MAX_TOKEN_BYTES:
                return Response(status_code=413, headers=_NO_STORE)
            payload.extend(chunk)
    except ClientDisconnect:
        return Response(status_code=400, headers=_NO_STORE)

    event = _EVENT_TOKENS.get(bytes(payload))
    if event is None:
        return Response(status_code=400, headers=_NO_STORE)

    try:
        await run_in_threadpool(_record_event, db, event)
    except SQLAlchemyError:
        logger.warning("Public site analytics event could not be recorded")
        return Response(status_code=503, headers=_NO_STORE)
    return Response(status_code=204, headers=_NO_STORE)


@router.get(
    "/admin/public-site/analytics",
    response_model=PublicSiteAnalyticsReportOut,
    operation_id="admin_get_public_site_analytics",
    responses={
        401: {"description": "Authentication required."},
        403: {"description": "Administrator role required."},
        503: {"description": "Report temporarily unavailable."},
    },
)
def admin_get_public_site_analytics(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicSiteAnalyticsReportOut:
    if current_user.role != "Admin" or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
            headers=_NO_STORE,
        )
    try:
        days = PublicSiteAnalyticsRepository(db).read_daily_totals(
            as_of=datetime.now(UTC)
        )
    except SQLAlchemyError:
        logger.warning("Public site analytics report unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Public site analytics unavailable",
            headers=_NO_STORE,
        ) from None

    response.headers.update(_NO_STORE)
    return PublicSiteAnalyticsReportOut(
        enabled=settings.PUBLIC_SITE_ANALYTICS_ENABLED,
        days=[PublicSiteAnalyticsDayOut.model_validate(day) for day in days],
    )
