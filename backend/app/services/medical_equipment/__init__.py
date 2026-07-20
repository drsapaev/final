"""medical_equipment — split from medical_equipment_service.py."""
from __future__ import annotations

from app.services.medical_equipment._base import *  # noqa: F401, F403
from app.services.medical_equipment._base import MedicalEquipmentServiceMixinBase
from app.services.medical_equipment._core import CoreMixin
from app.services.medical_equipment._operations import OperationsMixin

__all__ = ["MedicalEquipmentService"]


class MedicalEquipmentService(
    CoreMixin,
    OperationsMixin,
    MedicalEquipmentServiceMixinBase,
):
    """Composed of focused mixin modules."""

    def __init__(self, db: Session):
        self.db = db
        self.devices: dict[str, BaseDeviceDriver] = {}
        self.measurements: list[MeasurementData] = []
        self._initialize_devices()
