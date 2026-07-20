"""Orders mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import LabReportingServiceMixinBase


class OrdersMixin(LabReportingServiceMixinBase):
    """Orders methods for LabReportingService."""

    def list_orders(
        self,
        *,
        status: str | None,
        patient_id: int | None,
        limit: int,
        offset: int,
    ) -> list[LabOrder]:
        logger.info(
            "[LAB] list_orders status=%s has_patient_filter=%s limit=%s offset=%s",
            status,
            patient_id is not None,
            limit,
            offset,
        )
        return self.repository.list_orders(
            status=status,
            patient_id=patient_id,
            limit=limit,
            offset=offset,
        )

    # ============================================================
    # === TEMPLATE MANAGEMENT ===
    # ============================================================


