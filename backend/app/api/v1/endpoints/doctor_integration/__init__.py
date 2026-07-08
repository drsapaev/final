"""doctor_integration package — split from doctor_integration.py (1900 LOC).

Re-exports ``router`` for backward compatibility.
"""
from __future__ import annotations

from app.api.v1.endpoints.doctor_integration._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.doctor_integration._helpers import router

# Import all endpoint modules to register routes on the shared router.
from app.api.v1.endpoints.doctor_integration import _doctor_info  # noqa: F401
from app.api.v1.endpoints.doctor_integration import _queue_ops  # noqa: F401
from app.api.v1.endpoints.doctor_integration import _visits  # noqa: F401

__all__ = ["router"]
