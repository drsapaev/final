from __future__ import annotations

from datetime import datetime

import pytest

from app.models.lab import LabOrder
from app.repositories.lab_api_repository import LabApiRepository


@pytest.mark.unit
class TestLabApiRepository:
    def test_list_orders_applies_filters(self, db_session):
        db_session.add_all(
            [
                LabOrder(
                    patient_id=1,
                    visit_id=None,
                    status="done",
                    notes="ready",
                    created_at=datetime.utcnow(),
                ),
                LabOrder(
                    patient_id=2,
                    visit_id=None,
                    status="ordered",
                    notes="new",
                    created_at=datetime.utcnow(),
                ),
            ]
        )
        db_session.commit()
        repository = LabApiRepository(db_session)

        rows = repository.list_orders(
            status="done",
            patient_id=1,
            limit=10,
            offset=0,
        )

        assert len(rows) == 1
        assert rows[0].status == "done"

    def test_update_order_fields_mutates_row(self, db_session):
        row = LabOrder(
            patient_id=3,
            visit_id=None,
            status="ordered",
            notes=None,
            created_at=datetime.utcnow(),
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        repository = LabApiRepository(db_session)

        updated = repository.update_order_fields(row=row, notes="ok", status="done")

        assert updated.notes == "ok"
        assert updated.status == "done"

