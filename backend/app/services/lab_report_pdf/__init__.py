"""lab_report_pdf — split from lab_report_pdf_service.py.

Re-exports LabReportPDFService for backward compatibility.
"""
from __future__ import annotations

from app.services.lab_report_pdf._base import *  # noqa: F401, F403
from app.services.lab_report_pdf._base import LabReportPDFServiceMixinBase
from app.services.lab_report_pdf._core import CoreMixin
from app.services.lab_report_pdf._reportlab import ReportlabMixin
from app.services.lab_report_pdf._docx import DocxMixin

__all__ = ["LabReportPDFService"]


class LabReportPDFService(
    CoreMixin,
    ReportlabMixin,
    DocxMixin,
    LabReportPDFServiceMixinBase,
):
    """Composed of focused mixin modules."""

    def __init__(self) -> None:
        self.backend_root = Path(__file__).resolve().parents[2]
        self.templates_dir = self.backend_root / "app" / "templates" / "print"
        self.jinja_env = Environment(autoescape=True,
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )
