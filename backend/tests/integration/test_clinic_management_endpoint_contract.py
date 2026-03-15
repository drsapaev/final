from __future__ import annotations

import pytest

from app.api.v1.endpoints import clinic_management
from app.api.deps import require_admin
from app.crud.clinic_management import branch, equipment
from app.main import app
from app.schemas.clinic import BranchCreate, EquipmentCreate


def _create_branch(db_session, code: str):
    return branch.create(
        db=db_session,
        obj_in=BranchCreate(
            name=f"Branch {code}",
            code=code,
            address="Test address",
            status="active",
            timezone="Asia/Tashkent",
            capacity=50,
        ),
    )


def _create_equipment(db_session, *, branch_id: int, name: str):
    return equipment.create(
        db=db_session,
        obj_in=EquipmentCreate(
            name=name,
            model="X-1",
            serial_number=None,
            equipment_type="medical",
            branch_id=branch_id,
            cabinet="101",
            status="active",
            purchase_date=None,
            warranty_expires=None,
            cost=1000,
            supplier="Vendor",
            notes=None,
        ),
    )


@pytest.fixture
def admin_override(admin_user):
    app.dependency_overrides[require_admin] = lambda: admin_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.integration
def test_clinic_equipment_endpoint_keeps_unscoped_admin_list_behavior(
    client,
    db_session,
    admin_override,
):
    selected_branch = _create_branch(db_session, "C1")
    _create_equipment(db_session, branch_id=selected_branch.id, name="Ultrasound")

    response = client.get("/api/v1/clinic/equipment")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "Ultrasound"
    assert payload[0]["branch_id"] == selected_branch.id


@pytest.mark.integration
def test_clinic_equipment_endpoint_applies_branch_scope_when_present(
    client,
    db_session,
    admin_override,
    monkeypatch,
):
    in_scope_branch = _create_branch(db_session, "C2")
    out_of_scope_branch = _create_branch(db_session, "C3")
    _create_equipment(db_session, branch_id=in_scope_branch.id, name="ECG")
    _create_equipment(db_session, branch_id=out_of_scope_branch.id, name="MRI")

    monkeypatch.setattr(
        clinic_management,
        "_request_branch_scope",
        lambda _request: in_scope_branch.id,
    )

    list_response = client.get("/api/v1/clinic/equipment")

    assert list_response.status_code == 200
    payload = list_response.json()
    assert [item["name"] for item in payload] == ["ECG"]
    assert {item["branch_id"] for item in payload} == {in_scope_branch.id}

    blocked_create = client.post(
        "/api/v1/clinic/equipment",
        json={
            "name": "X-Ray",
            "model": "XR-2",
            "serial_number": None,
            "equipment_type": "medical",
            "branch_id": out_of_scope_branch.id,
            "cabinet": "102",
            "status": "active",
            "purchase_date": None,
            "warranty_expires": None,
            "cost": 1500,
            "supplier": "Vendor",
            "notes": None,
        },
    )

    assert blocked_create.status_code == 403
    assert "outside branch scope" in blocked_create.json()["detail"]
