"""
Registrar wizard package.

Re-exports router for backward compatibility.
"""
from app.api.v1.endpoints.registrar_wizard._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.registrar_wizard._helpers import router

# Import all endpoint modules to register routes on the router
from app.api.v1.endpoints.registrar_wizard import _invoice  # noqa: F401
from app.api.v1.endpoints.registrar_wizard import _cart  # noqa: F401
from app.api.v1.endpoints.registrar_wizard import _settings  # noqa: F401
from app.api.v1.endpoints.registrar_wizard import _visits  # noqa: F401

__all__ = ["router"]
