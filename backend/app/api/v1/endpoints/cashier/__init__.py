"""cashier package — split from cashier.py (1787 LOC).

Re-exports ``router`` for backward compatibility.
"""
from __future__ import annotations

from app.api.v1.endpoints.cashier import (
    _payments,  # noqa: F401
    _stats,  # noqa: F401
    _visits,  # noqa: F401
)
from app.api.v1.endpoints.cashier._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.cashier._helpers import router

__all__ = ["router"]
