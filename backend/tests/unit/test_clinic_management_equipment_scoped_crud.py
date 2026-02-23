from __future__ import annotations

import pytest

from app.crud.clinic_management import branch, equipment
from app.repositories.branch_scope_repository import BranchScopeViolationError
from app.schemas.clinic import BranchCreate, EquipmentCreate, EquipmentUpdate


def _create_branch(db, code: str):
    return branch.create(
        db=db,
        obj_in=BranchCreate(
            name=f"Branch {code}",
            code=code,
            address="Test address",
            status="active",
            timezone="Asia/Tashkent",
            capacity=50,
        ),
    )


def _equipment_payload(branch_id: int, name: str = "ECG Device") -> EquipmentCreate:
    return EquipmentCreate(
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
    )


def test_create_scoped_rejects_cross_branch_payload(db) -> None:
    first_branch = _create_branch(db, "B1")
    second_branch = _create_branch(db, "B2")

    with pytest.raises(BranchScopeViolationError):
        equipment.create_scoped(
            db=db,
            obj_in=_equipment_payload(branch_id=first_branch.id),
            branch_scope_id=second_branch.id,
        )


def test_create_and_get_scoped_within_same_branch(db) -> None:
    selected_branch = _create_branch(db, "B3")
    other_branch = _create_branch(db, "B4")

    created = equipment.create_scoped(
        db=db,
        obj_in=_equipment_payload(branch_id=selected_branch.id, name="Ultrasound"),
        branch_scope_id=selected_branch.id,
    )

    assert created.id is not None
    assert created.branch_id == selected_branch.id

    scoped_hit = equipment.get_scoped(
        db=db,
        id=created.id,
        branch_scope_id=selected_branch.id,
    )
    assert scoped_hit is not None
    assert scoped_hit.id == created.id

    scoped_miss = equipment.get_scoped(
        db=db,
        id=created.id,
        branch_scope_id=other_branch.id,
    )
    assert scoped_miss is None


def test_update_scoped_blocks_branch_reassignment(db) -> None:
    source_branch = _create_branch(db, "B5")
    target_branch = _create_branch(db, "B6")
    created = equipment.create(
        db=db,
        obj_in=_equipment_payload(branch_id=source_branch.id, name="Monitor"),
    )

    update_payload = EquipmentUpdate(branch_id=target_branch.id, name="Monitor v2")
    with pytest.raises(BranchScopeViolationError):
        equipment.update_scoped(
            db=db,
            db_obj=created,
            obj_in=update_payload,
            branch_scope_id=source_branch.id,
        )


def test_delete_scoped_only_deletes_inside_scope(db) -> None:
    first_branch = _create_branch(db, "B7")
    second_branch = _create_branch(db, "B8")
    created = equipment.create(
        db=db,
        obj_in=_equipment_payload(branch_id=first_branch.id, name="XRay"),
    )

    blocked_delete = equipment.delete_scoped(
        db=db,
        id=created.id,
        branch_scope_id=second_branch.id,
    )
    assert blocked_delete is None

    deleted = equipment.delete_scoped(
        db=db,
        id=created.id,
        branch_scope_id=first_branch.id,
    )
    assert deleted is not None
