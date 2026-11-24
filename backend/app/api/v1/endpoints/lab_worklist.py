import logging
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_roles
from app.crud.clinic import get_queue_settings
from app.repositories.lab_worklist_repository import (
    InvalidWorklistCursor,
    search_lab_worklist,
)
from app.schemas.lab_worklist import (
    LabCanceledOrderedTest,
    LabOrderedTestCancellation,
    LabWorklistPage,
    LabWorklistSearch,
)
from app.services.lab_ordered_test_service import cancel_unreported_lab_test
from app.services.lab_reporting_service import LabReportingDomainError
from app.services.patient_access_audit import log_patient_access_many

logger = logging.getLogger(__name__)


class _LabWorklistRoute(APIRoute):
    def get_route_handler(self):
        handle_request = super().get_route_handler()

        async def handle_lab_worklist(request: Request) -> Response:
            try:
                return await handle_request(request)
            except SQLAlchemyError as exc:
                # Driver exceptions can contain the bound search text.
                logger.error(
                    "Laboratory worklist database error: %s", type(exc).__name__
                )
                raise HTTPException(
                    status_code=503,
                    detail="Laboratory worklist temporarily unavailable",
                ) from None

        return handle_lab_worklist


router = APIRouter(prefix="/lab", tags=["lab-reporting"], route_class=_LabWorklistRoute)


@router.post("/worklist/search", response_model=LabWorklistPage)
def list_lab_worklist(
    payload: LabWorklistSearch,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user=Depends(require_active_roles("Admin", "Lab")),
):
    """Read a page of work and counters across the same search scope.

    The search body keeps patient names and barcode values out of URLs.
    """
    timezone = ZoneInfo(get_queue_settings(db).get("timezone", "Asia/Tashkent"))
    try:
        page = search_lab_worklist(db, payload, timezone)
    except InvalidWorklistCursor as exc:
        raise HTTPException(
            status_code=409, detail="Lab worklist cursor expired"
        ) from exc

    log_patient_access_many(
        db,
        actor_user=user,
        resource_entries=[(row.patient_id, row.id) for row in page.entries],
        resource_type="lab_worklist",
        action="read",
        request=request,
    )
    response.headers["Cache-Control"] = "no-store"
    return page


@router.post(
    "/visits/{visit_id}/tests/{visit_service_id}/cancel",
    response_model=LabCanceledOrderedTest,
)
def cancel_lab_ordered_test(
    visit_id: int,
    visit_service_id: int,
    payload: LabOrderedTestCancellation,
    db: Session = Depends(get_db),
    user=Depends(require_active_roles("Admin", "Lab")),
):
    try:
        return cancel_unreported_lab_test(
            db,
            visit_id=visit_id,
            visit_service_id=visit_service_id,
            order_id=payload.order_id,
            actor_id=user.id,
            reason=payload.reason,
        )
    except LabReportingDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
