"""
Regression (Sentry PYTHON-FASTAPI-M, post-redeploy events on GET /api/v1/schedule):
crud.list_schedules ordered by ScheduleTemplate.department.nulls_last(), but
`.department` is a relationship, not a column — the query raised and the
endpoint 500'd. Ordering now uses the real department_id/doctor_id columns;
this test pins that listing works and NULL department sorts last.
"""

from app.crud.schedule import list_schedules
from app.models.schedule import ScheduleTemplate


def test_list_schedules_orders_and_puts_null_department_last(db_session):
    db_session.add(
        ScheduleTemplate(
            weekday=1,
            start_time="08:00",
            end_time="12:00",
            department_id=7,
            doctor_id=3,
            active=True,
        )
    )
    db_session.add(
        ScheduleTemplate(
            weekday=1,
            start_time="09:00",
            end_time="13:00",
            department_id=None,
            doctor_id=None,
            active=True,
        )
    )
    db_session.commit()

    rows = list_schedules(db_session)

    assert len(rows) == 2
    # NULL department_id must be last (nulls_last), not raise
    assert rows[-1].department_id is None
    assert rows[0].department_id == 7
