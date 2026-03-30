from __future__ import annotations

from app.crud.message import message as message_crud
from app.models.message import Message
from app.schemas.message import MessageCreate


def test_create_persists_patient_id(db_session, test_patient, test_doctor_user):
    created = message_crud.create(
        db_session,
        sender_id=test_patient.id,
        obj_in=MessageCreate(
            recipient_id=test_doctor_user.id,
            content="Проверка patient_id",
            patient_id=test_patient.id,
        ),
    )

    persisted = db_session.query(Message).filter(Message.id == created.id).first()

    assert persisted is not None
    assert persisted.patient_id == test_patient.id
    assert persisted.sender_id == test_patient.id
    assert persisted.recipient_id == test_doctor_user.id
