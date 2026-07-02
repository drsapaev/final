from datetime import datetime
from decimal import Decimal

from app.api.v1.endpoints.registrar_wizard import (
    PriceOverrideListResponse,
    _price_override_available_actions,
)


def _price_override_response(status: str) -> PriceOverrideListResponse:
    available_actions = _price_override_available_actions(status)
    return PriceOverrideListResponse(
        id=1,
        visit_id=2,
        service_id=3,
        service_name="Consultation",
        doctor_name="Demo Doctor",
        doctor_specialty="dermatology",
        patient_name="Demo Patient",
        original_price=Decimal("100000.00"),
        new_price=Decimal("120000.00"),
        reason="requested discount change",
        details=None,
        status=status,
        available_actions=available_actions,
        can_approve="approve" in available_actions,
        can_reject="reject" in available_actions,
        created_at=datetime(2026, 1, 1),
    )


def test_pending_price_override_actions_are_backend_owned() -> None:
    row = _price_override_response("pending")

    assert row.available_actions == ["approve", "reject"]
    assert row.can_approve is True
    assert row.can_reject is True


def test_processed_price_override_actions_fail_closed() -> None:
    for status in ("approved", "rejected", "unknown"):
        row = _price_override_response(status)

        assert row.available_actions == []
        assert row.can_approve is False
        assert row.can_reject is False
