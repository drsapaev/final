"""The visit-level All Free decision shared by transaction entry points."""

from app.models.visit import Visit

ALL_FREE_DECISION_REQUIRED = "Визит All Free ожидает решения администратора"
ALL_FREE_DECIDED_STATUSES = ("approved", "rejected")


def awaits_all_free_decision(visit: Visit) -> bool:
    return (
        visit.discount_mode == "all_free"
        and visit.approval_status not in ALL_FREE_DECIDED_STATUSES
    )
