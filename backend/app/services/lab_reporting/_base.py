"""Service layer for laboratory templates, versions, instances, and PDF workflow."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.lab import (
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
from app.models.visit import Visit
from app.models.user import User
from app.models.clinic import Doctor
from app.repositories.lab_reporting_api_repository import LabReportingApiRepository
from app.services.canonical_visit_service import (
    CanonicalVisitResolutionError,
    CanonicalVisitService,
)
from app.services.lab_catalog_seed_data import (
    DEFAULT_LAB_ANALYTE_DEFINITIONS,
    DEFAULT_LAB_REFERENCE_RANGE_DEFINITIONS,
    DEFAULT_LAB_UNIT_DEFINITIONS,
)
from app.services.lab_seed_data import DEFAULT_LAB_TEMPLATE_DEFINITIONS
from app.services.lab_template_binding_seed_data import (
    DEFAULT_LAB_TEMPLATE_BINDING_DEFINITIONS,
)
from app.services.notifications import notification_sender_service
from app.services.service_mapping import normalize_service_code

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
