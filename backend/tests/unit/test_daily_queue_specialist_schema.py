from datetime import date

from sqlalchemy import Integer

from app.crud import online_queue as crud_queue
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue


def test_daily_queue_specialist_fk_matches_doctor_pk():
    specialist_id_column = DailyQueue.__table__.c.specialist_id
    doctor_id_column = Doctor.__table__.c.id

    assert isinstance(specialist_id_column.type, Integer)
    assert isinstance(doctor_id_column.type, Integer)

    foreign_keys = list(specialist_id_column.foreign_keys)
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "doctors.id"


def test_daily_queue_helper_canonicalizes_legacy_user_id_input(
    db_session,
    cardio_user,
    test_doctor,
):
    queue = crud_queue.get_or_create_daily_queue(
        db_session,
        day=date.today(),
        specialist_id=cardio_user.id,
        queue_tag="cardiology_common",
    )

    same_queue = crud_queue.get_or_create_daily_queue(
        db_session,
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
    )

    assert queue.id == same_queue.id
    assert queue.specialist_id == test_doctor.id
