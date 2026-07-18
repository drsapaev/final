"""Service layer for laboratory templates, versions, instances, and PDF workflow."""

from __future__ import annotations

import asyncio  # noqa: F401
import hashlib  # noqa: F401
import json  # noqa: F401
import logging  # noqa: F401
from copy import deepcopy  # noqa: F401
from dataclasses import dataclass  # noqa: F401
from datetime import UTC, date, datetime  # noqa: F401
from decimal import Decimal, InvalidOperation  # noqa: F401
from typing import Any  # noqa: F401

from sqlalchemy import func  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.models.appointment import Appointment  # noqa: F401
from app.models.clinic import Doctor  # noqa: F401
from app.models.lab import (  # noqa: F401
    FINAL_INSTANCE_STATUSES,
    LabCatalogAnalyte,
    LabCatalogReferenceRange,
    LabCatalogUnit,
    LabOrder,
    LabReportFieldDef,
    LabReportInstance,
    LabReportSection,
    LabReportTemplate,
    LabReportTemplateVersion,
    LabReportValue,
    LabResult,
    LabTemplateServiceBinding,
)
from app.models.user import User  # noqa: F401
from app.models.visit import Visit  # noqa: F401
from app.repositories.lab_reporting_api_repository import (
    LabReportingApiRepository,  # noqa: F401
)
from app.services.canonical_visit_service import (  # noqa: F401
    CanonicalVisitResolutionError,
    CanonicalVisitService,
)
from app.services.lab_catalog_seed_data import (  # noqa: F401
    DEFAULT_LAB_ANALYTE_DEFINITIONS,
    DEFAULT_LAB_REFERENCE_RANGE_DEFINITIONS,
    DEFAULT_LAB_UNIT_DEFINITIONS,
)
from app.services.lab_seed_data import DEFAULT_LAB_TEMPLATE_DEFINITIONS  # noqa: F401
from app.services.lab_template_binding_seed_data import (  # noqa: F401
    DEFAULT_LAB_TEMPLATE_BINDING_DEFINITIONS,
)
from app.services.notifications import notification_sender_service  # noqa: F401
from app.services.service_mapping import normalize_service_code  # noqa: F401

logger = logging.getLogger(__name__)

FLAG_SEVERITY_RANKS = {
    "warning": 100,
    "low": 200,
    "high": 200,
    "abnormal": 250,
    "critical": 300,
}


@dataclass
class LabReportingDomainError(Exception):
    status_code: int
    detail: str




class LabReportingServiceMixinBase:
    """Type-hint anchor for LabReportingService mixins."""
