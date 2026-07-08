"""Backward-compatible shim for reporting_svc package."""
from __future__ import annotations
from app.services.reporting_svc import ReportingService
from app.services.reporting_svc._reports import get_reporting_service

__all__ = ["ReportingService"]
