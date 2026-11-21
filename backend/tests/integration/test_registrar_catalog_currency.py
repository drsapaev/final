"""The registrar catalog must not invent price or currency for legacy rows."""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import update

from app.models.service import Service
from tests.conftest import mint_access_token


@pytest.mark.integration
def test_catalog_preserves_usd_zero_and_unknown_values(client, db_session, admin_user):
    suffix = uuid4().hex[:10]
    rows = [
        Service(code=f"P1{suffix}", name="SYNTHETIC USD", price=Decimal("100.00"), currency="USD", active=True),
        Service(code=f"P2{suffix}", name="SYNTHETIC free", price=Decimal("0.00"), currency="UZS", active=True),
        Service(code=f"P3{suffix}", name="SYNTHETIC unknown", price=Decimal("1.00"), currency="UZS", active=True),
    ]
    db_session.add_all(rows)
    db_session.flush()
    ids = [row.id for row in rows]
    db_session.execute(update(Service).where(Service.id == ids[2]).values(price=None, currency=None))
    db_session.commit()
    db_session.expire_all()
    response = client.get("/api/v1/registrar/services", headers={"Authorization": f"Bearer {mint_access_token(admin_user)}"})
    assert response.status_code == 200, response.text
    all_services = [row for group in response.json()["services_by_group"].values() for row in group]
    by_id = {row["id"]: row for row in all_services if row["id"] in ids}
    assert by_id[ids[0]]["price"] == 100 and by_id[ids[0]]["currency"] == "USD"
    assert by_id[ids[1]]["price"] == 0 and by_id[ids[1]]["currency"] == "UZS"
    assert by_id[ids[2]]["price"] is None and by_id[ids[2]]["currency"] is None
