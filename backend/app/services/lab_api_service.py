"""Compatibility service boundary for legacy lab API checks."""

from __future__ import annotations

from app.services.lab_reporting_service import LabReportingService


class LabApiService(LabReportingService):
    """Compatibility alias for the lab API service layer."""

    pass


# --- API Router moved from app/api/v1/endpoints/lab.py ---
