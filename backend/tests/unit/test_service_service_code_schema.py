from sqlalchemy import String

from app.models.service import Service


def test_service_code_schema_accepts_legitimate_runtime_values():
    column = Service.__table__.c.service_code

    assert isinstance(column.type, String)
    assert column.type.length == 32

    assert len("W2C-QR-LAB-EXISTING") <= column.type.length
    assert len("cardiology_consult") <= column.type.length
    assert len("D_PROC01") <= column.type.length
