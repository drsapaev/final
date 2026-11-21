"""The visit-level All Free decision shared by transaction entry points."""

from sqlalchemy import and_, func
from sqlalchemy.sql.elements import ColumnElement

from app.models.visit import Visit

ALL_FREE_DECISION_REQUIRED = "Визит All Free ожидает решения администратора"
ALL_FREE_DECIDED_STATUSES = ("approved", "rejected")


def awaits_all_free_decision(visit: Visit) -> bool:
    return (
        visit.discount_mode == "all_free"
        and visit.approval_status not in ALL_FREE_DECIDED_STATUSES
    )


def all_free_decision_required_clause() -> ColumnElement[bool]:
    return and_(
        func.coalesce(Visit.discount_mode, "none") == "all_free",
        func.coalesce(Visit.approval_status, "none").notin_(ALL_FREE_DECIDED_STATUSES),
    )
