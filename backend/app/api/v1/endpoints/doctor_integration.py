"""Backward-compatible shim for the doctor_integration package.

Originally a 1900-LOC god file — now split into focused endpoint
modules under :mod:`app.api.v1.endpoints.doctor_integration`.
"""
from __future__ import annotations

from app.api.v1.endpoints.doctor_integration import router

__all__ = ["router"]
