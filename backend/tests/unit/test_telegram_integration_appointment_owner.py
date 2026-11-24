"""A clinical delivery needs an unambiguous canonical resource identifier."""

import pytest
from fastapi import HTTPException

from app.services.telegram_delivery_authorization import _required_id


@pytest.mark.parametrize("payload", [{}, {"id": None}, {"id": True}, {"id": 1.5},
                                  {"id": "1.5"}, {"id": -1},
                                  {"id": 1, "appointment_id": 2}])
def test_missing_or_ambiguous_resource_id_fails_closed(payload):
    with pytest.raises(HTTPException) as exc:
        _required_id(payload, ("appointment_id", "id"))
    assert exc.value.status_code == 400


def test_equivalent_resource_ids_are_accepted():
    assert _required_id({"id": "7", "appointment_id": 7}, ("appointment_id", "id")) == 7
