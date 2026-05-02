"""Compatibility service boundary for legacy EMR v2 API checks."""

from __future__ import annotations

from app.services.emr_v2_service import EMRV2Service


class EMRV2ApiService(EMRV2Service):
    """Compatibility alias for the EMR v2 API service layer."""

    pass


# --- API Router moved from app/api/v1/endpoints/emr_v2.py ---
