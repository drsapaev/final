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


# Perf (P0 2026-09-03): the self-heal seeders are idempotent but expensive —
# hundreds of per-row statements per call (~20s+ on the remote Supabase), and
# they ran on EVERY read/resolve/create. They are process-cached after the
# first successful pass: lab templates/catalog rows only change via admin
# tooling or migrations, and self-heal is re-armed on a template 404
# (see TemplatesMixin.get_template) so accidental data loss still recovers.
_SEED_ENSURED = {"bind_id": None, "catalog": False, "templates": False, "bindings": False}


def _seed_cache_fresh(bind: object, part: str) -> bool:
    """False when this part was already ensured FOR THE CURRENT bind.

    Tests build a fresh database per test while the process lives on, so the
    cache is keyed by the bind object identity — a new engine re-runs the
    seeders, the production engine keeps the once-per-process win.
    """
    if _SEED_ENSURED.get("bind_id") != id(bind):
        # A NEW bind resets every part: per-part flags belonged to the
        # previous database (tests roll data back between cases).
        _SEED_ENSURED.update(
            bind_id=id(bind), catalog=False, templates=False, bindings=False,
            templates_sig=None,
        )
    return not _SEED_ENSURED.get(part, False)


def _template_definitions_signature(definitions: list[dict]) -> str:
    import hashlib
    import json

    return hashlib.sha256(
        json.dumps(definitions, sort_keys=True, ensure_ascii=False, default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def _mark_seed_ensured(bind: object, part: str) -> None:
    _SEED_ENSURED["bind_id"] = id(bind)
    _SEED_ENSURED[part] = True


def reset_lab_seed_cache() -> None:
    """Re-arm the self-heal seeders (e.g. a template lookup came up empty)."""
    _SEED_ENSURED["catalog"] = False
    _SEED_ENSURED["templates"] = False
    _SEED_ENSURED["bindings"] = False
