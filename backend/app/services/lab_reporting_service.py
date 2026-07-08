"""Backward-compatible shim for lab_reporting package.

Originally a 2450-LOC god file — now split into focused mixin modules
under :mod:`app.services.lab_reporting`.
"""
from __future__ import annotations

from app.services.lab_reporting import LabReportingService
from app.services.lab_reporting._base import (
    FLAG_SEVERITY_RANKS,
    LabReportingDomainError,
)
from app.services.lab_reporting._base import (
    DEFAULT_LAB_ANALYTE_DEFINITIONS,
    DEFAULT_LAB_REFERENCE_RANGE_DEFINITIONS,
    DEFAULT_LAB_TEMPLATE_BINDING_DEFINITIONS,
    DEFAULT_LAB_TEMPLATE_DEFINITIONS,
    DEFAULT_LAB_UNIT_DEFINITIONS,
)

__all__ = [
    "LabReportingService",
    "LabReportingDomainError",
    "FLAG_SEVERITY_RANKS",
    "DEFAULT_LAB_ANALYTE_DEFINITIONS",
    "DEFAULT_LAB_REFERENCE_RANGE_DEFINITIONS",
    "DEFAULT_LAB_TEMPLATE_BINDING_DEFINITIONS",
    "DEFAULT_LAB_TEMPLATE_DEFINITIONS",
    "DEFAULT_LAB_UNIT_DEFINITIONS",
]
