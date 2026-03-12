from sqlalchemy import Integer

from app.models.doctor_templates import DoctorTreatmentTemplate
from app.models.user import User


def test_doctor_treatment_template_doctor_fk_matches_user_pk():
    doctor_id_column = DoctorTreatmentTemplate.__table__.c.doctor_id
    user_id_column = User.__table__.c.id

    assert isinstance(doctor_id_column.type, Integer)
    assert isinstance(user_id_column.type, Integer)

    foreign_keys = list(doctor_id_column.foreign_keys)
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "users.id"
