"""
Registrar integration package.

Re-exports router and key functions for backward compatibility.
"""
# Import endpoint modules to register routes
from app.api.v1.endpoints.registrar_integration import (
    _departments,  # noqa: F401
    _queue_ops,  # noqa: F401
    _queue_profiles,  # noqa: F401
    _services_doctors,  # noqa: F401
    _today_queues,  # noqa: F401
)
from app.api.v1.endpoints.registrar_integration._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.registrar_integration._helpers import (  # noqa: F401
    _registrar_available_actions,
    _serialize_registrar_datetime,
    router,
)

# Re-export functions used by other modules
from app.api.v1.endpoints.registrar_integration._queue_ops import (
    start_queue_visit,  # noqa: F401
)
from app.api.v1.endpoints.registrar_integration._today_queues import (
    get_today_queues,  # noqa: F401
)

__all__ = [
    "router",
    "get_today_queues",
    "start_queue_visit",
    "_serialize_registrar_datetime",
    "_registrar_available_actions",
]
