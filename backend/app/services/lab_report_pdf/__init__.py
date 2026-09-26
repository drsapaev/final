"""lab_report_pdf — split from lab_report_pdf_service.py.

Re-exports LabReportPDFService for backward compatibility.
"""
from __future__ import annotations

from app.services.lab_report_pdf._base import *  # noqa: F401, F403
from app.services.lab_report_pdf._base import LabReportPDFServiceMixinBase
from app.services.lab_report_pdf._core import CoreMixin
from app.services.lab_report_pdf._docx import DocxMixin
from app.services.lab_report_pdf._reportlab import ReportlabMixin

__all__ = ["LabReportPDFService"]


class LabReportPDFService(
    CoreMixin,
    ReportlabMixin,
    DocxMixin,
    LabReportPDFServiceMixinBase,
):
    """Composed of focused mixin modules."""

    def __init__(self) -> None:
        # PR8 hotfix: parents[2] после сплита в пакет указывал на backend/app,
        # а шаблоны лежат в backend/app/templates/print — нужен parents[3].
        self.backend_root = Path(__file__).resolve().parents[3]
        self.templates_dir = self.backend_root / "app" / "templates" / "print"
        self.jinja_env = Environment(autoescape=True,
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )
