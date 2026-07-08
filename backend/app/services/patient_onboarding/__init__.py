"""patient_onboarding — split from patient_onboarding_service.py."""
from __future__ import annotations

from app.services.patient_onboarding._base import *  # noqa: F401, F403
from app.services.patient_onboarding._base import PatientOnboardingServiceMixinBase
from app.services.patient_onboarding._core import CoreMixin
from app.services.patient_onboarding._processing import ProcessingMixin
from app.services.patient_onboarding._review import ReviewMixin

__all__ = ["PatientOnboardingService"]


class PatientOnboardingService(
    CoreMixin,
    ProcessingMixin,
    ReviewMixin,
    PatientOnboardingServiceMixinBase,
):
    """Composed of focused mixin modules."""

    def __init__(self, db: Session) -> None:
        self.db = db
