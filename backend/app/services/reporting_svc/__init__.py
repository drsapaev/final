"""reporting_svc — split from reporting_service.py."""
from __future__ import annotations
from app.services.reporting_svc._base import *  # noqa: F401, F403
from app.services.reporting_svc._base import ReportingServiceMixinBase
from app.services.reporting_svc._core import CoreMixin
from app.services.reporting_svc._reports import ReportsMixin

__all__ = ["ReportingService"]


class ReportingService(
    CoreMixin,
    ReportsMixin,
    ReportingServiceMixinBase,
):
    """Composed of focused mixin modules."""

    def __init__(self, db: Session):
        self.db = db
        self.reports_dir = "reports"
        os.makedirs(self.reports_dir, exist_ok=True)
