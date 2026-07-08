"""Backward-compatible shim for lab_report_pdf package."""
from __future__ import annotations

from app.services.lab_report_pdf import LabReportPDFService  # noqa: F401

lab_report_pdf_service = LabReportPDFService()

__all__ = ["LabReportPDFService", "lab_report_pdf_service"]
