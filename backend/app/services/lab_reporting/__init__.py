"""lab_reporting — split from lab_reporting_service.py.

Re-exports LabReportingService for backward compatibility.
"""
from __future__ import annotations

from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import (
    LabCatalogAnalyte,
    LabCatalogReferenceRange,
    LabCatalogUnit,
    LabReportingApiRepository,
    LabReportingServiceMixinBase,
)
from app.services.lab_reporting._catalog import CatalogMixin
from app.services.lab_reporting._catalog_helpers import CatalogHelpersMixin
from app.services.lab_reporting._context import ContextMixin
from app.services.lab_reporting._finalize import FinalizeMixin
from app.services.lab_reporting._instances import InstancesMixin
from app.services.lab_reporting._materialization import MaterializationMixin
from app.services.lab_reporting._orders import OrdersMixin
from app.services.lab_reporting._payload import PayloadMixin
from app.services.lab_reporting._rule_engine import RuleEngineMixin
from app.services.lab_reporting._templates import TemplatesMixin
from app.services.lab_reporting._versions import VersionsMixin

__all__ = ["LabReportingService"]


class LabReportingService(
    OrdersMixin,
    TemplatesMixin,
    CatalogMixin,
    VersionsMixin,
    InstancesMixin,
    FinalizeMixin,
    MaterializationMixin,
    ContextMixin,
    PayloadMixin,
    CatalogHelpersMixin,
    RuleEngineMixin,
    LabReportingServiceMixinBase,
):
    """Composed of focused mixin modules under lab_reporting/."""

    def __init__(
        self,
        db: Session,
        repository: LabReportingApiRepository | None = None,
    ):
        self.db = db
        self.repository = repository or LabReportingApiRepository(db)
        self._catalog_unit_cache: dict[str, LabCatalogUnit | None] = {}
        self._catalog_analyte_cache: dict[str, LabCatalogAnalyte | None] = {}
        self._catalog_reference_cache: dict[str, list[LabCatalogReferenceRange]] = {}

    # ============================================================
    # === ORDER LISTING ===
    # ============================================================
