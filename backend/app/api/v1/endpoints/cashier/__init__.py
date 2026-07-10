"""cashier package — split from cashier.py (1787 LOC).

Re-exports ``router`` for backward compatibility.
"""
from __future__ import annotations

# Import order matters: ``_stats`` registers ``/payments/export`` (a static
# route) which must come BEFORE ``_payments`` registers ``/payments/{payment_id}``
# to avoid the parameter route shadowing the static export route. See the
# ``test_published_fastapi_routes_do_not_shadow_static_paths_across_routers``
# contract test for details.
from app.api.v1.endpoints.cashier import (
    _stats,  # noqa: F401
    _payments,  # noqa: F401
    _visits,  # noqa: F401
)
from app.api.v1.endpoints.cashier._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.cashier._helpers import router

__all__ = ["router"]
