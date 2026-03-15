from sqlalchemy import String

from app.models.enums import VisitStatus
from app.models.visit import Visit


def test_visit_status_schema_accepts_current_runtime_status_values():
    column = Visit.__table__.c.status

    assert isinstance(column.type, String)
    assert column.type.length == 20

    confirmed_statuses = {status.value for status in VisitStatus}
    confirmed_statuses.update({"scheduled", "expired", "canceled"})

    assert "pending_confirmation" in confirmed_statuses
    assert max(len(status) for status in confirmed_statuses) <= column.type.length
