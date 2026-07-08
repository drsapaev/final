"""Backward-compatible shim for medical_equipment package."""
from __future__ import annotations

from app.services.medical_equipment import MedicalEquipmentService  # noqa: F401
from app.services.medical_equipment._base import (  # noqa: F401
    ConnectionType,
    DeviceStatus,
    DeviceType,
)
from app.services.medical_equipment._operations import (
    get_medical_equipment_service,  # noqa: F401
)

__all__ = [
    "MedicalEquipmentService",
    "ConnectionType",
    "DeviceStatus",
    "DeviceType",
    "get_medical_equipment_service",
]
