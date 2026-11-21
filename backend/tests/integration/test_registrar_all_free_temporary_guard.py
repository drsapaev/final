"""Policy values that must keep registrar All Free requests pending."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints.registrar_wizard import _cart
from app.models.all_free_request import AllFreeRequest
from app.models.clinic import ClinicSettings
from app.models.payment_invoice import PaymentInvoice
from app.models.visit import Visit
from tests.integration.test_all_free_registrar_workflow import (
    migrated_visit_confirmation_context,  # noqa: F401 - pytest fixture import
)
from tests.integration.test_registrar_cart_encounter_grouping import (
    _headers,
    _service,
    _visit,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("migrated_visit_confirmation_context"),
]

@pytest.mark.parametrize("configured", [None, False, "false", "0", "garbage"])
@pytest.mark.parametrize("flag,mode", [(True, "none"), (False, "all_free"), (True, "benefit")])
def test_unapproved_all_free_stages_ordinary_prices_and_waits(
    client, db_session, admin_user, test_patient, configured, flag, mode, monkeypatch
):
    notify = AsyncMock(return_value=True)
    monkeypatch.setattr(_cart.notification_sender_service, "send_all_free_request_notification", notify)
    setting = db_session.query(ClinicSettings).filter_by(key="all_free_auto_approve").first()
    if setting is not None:
        db_session.delete(setting)
        db_session.flush()
    if configured is not None:
        db_session.add(ClinicSettings(key="all_free_auto_approve", value=configured, category="benefits"))
    db_session.commit()
    service = _service(db_session)
    response = client.post(
        "/api/v1/registrar/cart", headers=_headers(admin_user),
        json={"patient_id": test_patient.id, "discount_mode": mode, "all_free": flag,
              "payment_method": "cash", "visits": [_visit(service.id, date.today() + timedelta(days=1))]},
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    visit_id = response.json()["visit_ids"][0]
    visit = db_session.get(Visit, visit_id)
    request = db_session.query(AllFreeRequest).filter_by(visit_id=visit_id).one()
    invoice = db_session.get(PaymentInvoice, response.json()["invoice_id"])
    assert visit.status == "pending_confirmation"
    assert visit.confirmation_token is None
    assert request.status == "pending" and request.policy_auto_approve is False
    assert request.baseline_total == invoice.total_amount == Decimal("100.00")
    assert invoice.status == "pending"
    notify.assert_awaited_once()
