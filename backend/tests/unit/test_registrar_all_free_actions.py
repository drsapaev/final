from datetime import datetime
from decimal import Decimal

from app.api.v1.endpoints.registrar_wizard import (
    AllFreeVisitResponse,
    _all_free_available_actions,
)


def _all_free_response(approval_status: str) -> AllFreeVisitResponse:
    available_actions = _all_free_available_actions(approval_status)
    return AllFreeVisitResponse(
        id=1,
        patient_id=2,
        patient_name="Demo Patient",
        patient_phone="+998901234567",
        services=["Consultation"],
        total_original_amount=Decimal("150000.00"),
        doctor_name="Demo Doctor",
        doctor_specialty="cardiology",
        visit_date=None,
        visit_time=None,
        notes=None,
        created_at=datetime(2026, 1, 1),
        approval_status=approval_status,
        available_actions=available_actions,
        can_approve="approve" in available_actions,
        can_reject="reject" in available_actions,
    )


def test_pending_all_free_actions_are_backend_owned() -> None:
    row = _all_free_response("pending")

    assert row.available_actions == ["approve", "reject"]
    assert row.can_approve is True
    assert row.can_reject is True


def test_processed_all_free_actions_fail_closed() -> None:
    for approval_status in ("approved", "rejected", "none", "unknown"):
        row = _all_free_response(approval_status)

        assert row.available_actions == []
        assert row.can_approve is False
        assert row.can_reject is False
