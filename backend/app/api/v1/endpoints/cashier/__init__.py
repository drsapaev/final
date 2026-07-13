"""cashier package — split from cashier.py (1787 LOC).

Re-exports ``router`` for backward compatibility.

Import order matters: ``_stats`` registers ``/payments/export`` (a static
route) which must come BEFORE ``_payments`` registers ``/payments/{payment_id}``
to avoid the parameter route shadowing the static export route.
"""
from __future__ import annotations

from app.api.v1.endpoints.cashier import (
    _payments,  # noqa: F401  — registers /payments/{payment_id}
    _stats,  # noqa: F401  — must be first: registers /payments/export
    _visits,  # noqa: F401
)
from app.api.v1.endpoints.cashier._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.cashier._helpers import router

__all__ = ["router"]
