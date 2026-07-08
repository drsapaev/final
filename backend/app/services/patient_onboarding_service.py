"""Backward-compatible shim for patient_onboarding package."""
from __future__ import annotations
from app.services.patient_onboarding import PatientOnboardingService

__all__ = ["PatientOnboardingService"]
