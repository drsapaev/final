"""Service layer for visits endpoints."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import MetaData, Table, select, text
from sqlalchemy.orm import Session

from app.core.audit import extract_model_changes, log_critical_change
from app.models.visit import Visit
from app.repositories.visits_api_repository import VisitsApiRepository
from app.services.service_mapping import normalize_service_code


class VisitsApiService:
    """Handles visit listing, creation, status and reschedule flows."""

    def __init__(
        self,
        db: Session,
        repository: VisitsApiRepository | None = None,
    ):
        self.repository = repository or VisitsApiRepository(db)

    def _visits(self) -> Table:
        md = MetaData()
        return Table("visits", md, autoload_with=self.repository.get_bind())

    def _vservices(self) -> Table:
        md = MetaData()
        return Table("visit_services", md, autoload_with=self.repository.get_bind())

    def list_visits(
        self,
        *,
        patient_id: int | None,
        doctor_id: int | None,
        status_q: str | None,
        planned: date | None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        table = self._visits()
        stmt = select(table)
        if patient_id is not None:
            stmt = stmt.where(table.c.patient_id == patient_id)
        if doctor_id is not None:
            stmt = stmt.where(table.c.doctor_id == doctor_id)
        if status_q:
            stmt = stmt.where(table.c.status == status_q)
        if planned is not None:
            if "planned_date" in table.c:
                stmt = stmt.where(table.c.planned_date == planned)
            else:
                return []
        stmt = stmt.order_by(table.c.id.desc()).limit(limit).offset(offset)
        rows = self.repository.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    def create_visit(
        self,
        *,
        request,
        payload,
        current_user,
    ) -> dict[str, Any]:
        use_crud = os.getenv("USE_CRUD_VISITS", "false").lower() == "true"

        if use_crud:
            from app.crud.visit import create_visit as crud_create_visit

            visit = crud_create_visit(
                db=self.repository.db,
                patient_id=payload.patient_id,
                doctor_id=payload.doctor_id,
                visit_date=payload.planned_date,
                notes=payload.notes,
                status="open",
                auto_status=False,
                notify=False,
                log=True,
            )

            _, new_data = extract_model_changes(None, visit)
            log_critical_change(
                db=self.repository.db,
                user_id=getattr(current_user, "id", None) or 0,
                action="CREATE",
                table_name="visits",
                row_id=visit.id,
                old_data=None,
                new_data=new_data,
                request=request,
                description=f"Создан визит ID={visit.id}",
            )
            self.repository.commit()

            return {
                "id": visit.id,
                "patient_id": visit.patient_id,
                "doctor_id": visit.doctor_id,
                "status": visit.status,
                "created_at": visit.created_at,
                "started_at": None,
                "finished_at": None,
                "notes": visit.notes,
                "planned_date": visit.visit_date,
            }

        table = self._visits()
        ins_values = {
            "patient_id": payload.patient_id,
            "doctor_id": payload.doctor_id,
            "status": "open",
            "notes": payload.notes,
            "created_at": datetime.utcnow(),
            "discount_mode": "none",
            "approval_status": "none",
        }
        if hasattr(table.c, "planned_date") and payload.planned_date is not None:
            ins_values["planned_date"] = payload.planned_date

        ins = table.insert().values(**ins_values).returning(table)
        row = self.repository.execute(ins).mappings().first()
        if row is None:
            raise HTTPException(status_code=500, detail="Не удалось создать визит")

        visit_id = row["id"]
        new_data = {}
        for key, value in dict(row).items():
            if isinstance(value, datetime):
                new_data[key] = value.isoformat()
            elif isinstance(value, date):
                new_data[key] = value.isoformat()
            else:
                new_data[key] = value

        log_critical_change(
            db=self.repository.db,
            user_id=getattr(current_user, "id", None) or 0,
            action="CREATE",
            table_name="visits",
            row_id=visit_id,
            old_data=None,
            new_data=new_data,
            request=request,
            description=f"Создан визит ID={visit_id}",
        )
        self.repository.commit()
        return dict(row)

    def get_visit(self, *, visit_id: int) -> dict[str, Any]:
        visits_table = self._visits()
        services_table = self._vservices()
        visit_row = self.repository.execute(
            select(visits_table).where(visits_table.c.id == visit_id)
        ).mappings().first()
        if not visit_row:
            raise HTTPException(404, "Visit not found")

        services = (
            self.repository.execute(
                select(services_table)
                .where(services_table.c.visit_id == visit_id)
                .order_by(services_table.c.id.asc())
            )
            .mappings()
            .all()
        )
        return {"visit": dict(visit_row), "services": [dict(item) for item in services]}

    def add_service(self, *, visit_id: int, item) -> dict[str, Any]:
        visits_table = self._visits()
        services_table = self._vservices()
        exists = self.repository.execute(
            select(visits_table.c.id).where(visits_table.c.id == visit_id)
        ).first()
        if not exists:
            raise HTTPException(404, "Visit not found")

        normalized_code = normalize_service_code(item.code) if item.code else None
        ins = (
            services_table.insert()
            .values(
                visit_id=visit_id,
                code=normalized_code,
                name=item.name,
                price=item.price,
                qty=item.qty,
            )
            .returning(services_table)
        )
        row = self.repository.execute(ins).mappings().first()
        self.repository.commit()
        return {"ok": True, "service": dict(row) if row else None}

    def set_status(self, *, visit_id: int, status_new: str) -> Visit:
        if status_new not in {"open", "in_progress", "closed", "canceled"}:
            raise HTTPException(400, "Invalid status")

        visit = self.repository.query_visit(visit_id)
        if not visit:
            raise HTTPException(404, "Visit not found")

        visit.status = status_new
        if status_new == "in_progress":
            visit.started_at = datetime.utcnow()
        if status_new in {"closed", "canceled"}:
            visit.finished_at = datetime.utcnow()

        if status_new == "canceled":
            try:
                self.repository.execute(
                    text(
                        "UPDATE queue_entries SET status = 'canceled' WHERE visit_id = :visit_id"
                    ),
                    {"visit_id": visit_id},
                )
            except Exception:
                pass

        self.repository.commit()
        self.repository.refresh(visit)
        return visit

    def reschedule_visit(self, *, visit_id: int, new_date: date) -> dict[str, Any]:
        table = self._visits()
        if not hasattr(table.c, "visit_date"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="visits table has no visit_date column; check your schema.",
            )

        visit_row = self.repository.execute(
            select(table).where(table.c.id == visit_id)
        ).mappings().first()
        if not visit_row:
            raise HTTPException(404, "Visit not found")

        if visit_row.get("status") in {"closed", "canceled"}:
            raise HTTPException(
                status_code=409,
                detail="Cannot reschedule closed or canceled visit",
            )
        if visit_row.get("started_at"):
            raise HTTPException(
                status_code=409,
                detail="Cannot reschedule a visit that has been started",
            )

        upd = table.update().where(table.c.id == visit_id).values(visit_date=new_date).returning(table)
        row = self.repository.execute(upd).mappings().first()
        if not row:
            raise HTTPException(404, "Visit not found")

        try:
            self.repository.execute(
                text(
                    "UPDATE queue_entries SET status = 'rescheduled' WHERE visit_id = :visit_id"
                ),
                {"visit_id": visit_id},
            )
        except Exception:
            pass

        self.repository.commit()
        return dict(row)

    def reschedule_visit_tomorrow(self, *, visit_id: int) -> dict[str, Any]:
        tomorrow = date.today() + timedelta(days=1)
        return self.reschedule_visit(visit_id=visit_id, new_date=tomorrow)
