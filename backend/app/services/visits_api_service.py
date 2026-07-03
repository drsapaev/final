"""Service layer for visits endpoints."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import MetaData, Table, select, text
from sqlalchemy.orm import Session

from app.core.audit import extract_model_changes
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

    def _patients(self) -> Table:
        md = MetaData()
        return Table("patients", md, autoload_with=self.repository.get_bind())

    def _doctors(self) -> Table:
        md = MetaData()
        return Table("doctors", md, autoload_with=self.repository.get_bind())

    def _users(self) -> Table:
        md = MetaData()
        return Table("users", md, autoload_with=self.repository.get_bind())

    def _update_queue_entries_for_visit_owner(
        self,
        *,
        visit_id: int,
        patient_id: int | None,
        status_value: str,
    ) -> None:
        if patient_id is None:
            return

        self.repository.execute(
            text(
                """
                UPDATE queue_entries
                SET status = :status_value
                WHERE visit_id = :visit_id
                  AND patient_id = :patient_id
                """
            ),
            {
                "status_value": status_value,
                "visit_id": visit_id,
                "patient_id": patient_id,
            },
        )

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
            visit = self.repository.create_visit_via_crud(
                patient_id=payload.patient_id,
                doctor_id=payload.doctor_id,
                visit_date=payload.planned_date,
                notes=payload.notes,
                source=payload.source,
            )

            _, new_data = extract_model_changes(None, visit)
            self.repository.log_critical_change(
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
                "source": getattr(visit, "source", None) or payload.source or "desk",
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
        if hasattr(table.c, "source"):
            ins_values["source"] = payload.source or "desk"

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

        self.repository.log_critical_change(
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
        visit = dict(visit_row)

        patient_id = visit.get("patient_id")
        if patient_id:
            patients_table = self._patients()
            patient_row = self.repository.execute(
                select(
                    patients_table.c.id,
                    patients_table.c.last_name,
                    patients_table.c.first_name,
                    patients_table.c.middle_name,
                    patients_table.c.birth_date,
                    patients_table.c.phone,
                    patients_table.c.address,
                ).where(patients_table.c.id == patient_id)
            ).mappings().first()
            if patient_row:
                patient = dict(patient_row)
                patient_name = " ".join(
                    str(patient.get(key) or "").strip()
                    for key in ("last_name", "first_name", "middle_name")
                ).strip()
                birth_date = patient.get("birth_date")
                birth_year = getattr(birth_date, "year", None)
                visit.update(
                    {
                        "patient_name": patient_name,
                        "patient_fio": patient_name,
                        "patient_phone": patient.get("phone"),
                        "patient_birth_year": birth_year,
                        "birth_year": birth_year,
                        "address": patient.get("address"),
                        "patient": {
                            "id": patient.get("id"),
                            "full_name": patient_name,
                            "phone": patient.get("phone"),
                            "birth_year": birth_year,
                            "address": patient.get("address"),
                        },
                    }
                )

        doctor_id = visit.get("doctor_id")
        if doctor_id:
            doctors_table = self._doctors()
            users_table = self._users()
            doctor_row = self.repository.execute(
                select(
                    doctors_table.c.id,
                    doctors_table.c.specialty,
                    doctors_table.c.cabinet,
                    users_table.c.full_name.label("doctor_full_name"),
                    users_table.c.username.label("doctor_username"),
                )
                .select_from(
                    doctors_table.outerjoin(
                        users_table, users_table.c.id == doctors_table.c.user_id
                    )
                )
                .where(doctors_table.c.id == doctor_id)
            ).mappings().first()
            if doctor_row:
                doctor = dict(doctor_row)
                doctor_name = (
                    doctor.get("doctor_full_name")
                    or doctor.get("doctor_username")
                    or f"Doctor #{doctor_id}"
                )
                visit.update(
                    {
                        "doctor_name": doctor_name,
                        "room": doctor.get("cabinet"),
                        "doctor": {
                            "id": doctor.get("id"),
                            "name": doctor_name,
                            "specialty": doctor.get("specialty"),
                            "cabinet": doctor.get("cabinet"),
                        },
                    }
                )

        services = (
            self.repository.execute(
                select(services_table)
                .where(services_table.c.visit_id == visit_id)
                .order_by(services_table.c.id.asc())
            )
            .mappings()
            .all()
        )
        return {"visit": visit, "services": [dict(item) for item in services]}

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
                self._update_queue_entries_for_visit_owner(
                    visit_id=visit_id,
                    patient_id=visit.patient_id,
                    status_value="canceled",
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
            self._update_queue_entries_for_visit_owner(
                visit_id=visit_id,
                patient_id=visit_row.get("patient_id"),
                status_value="rescheduled",
            )
        except Exception:
            pass

        self.repository.commit()
        return dict(row)

    def reschedule_visit_tomorrow(self, *, visit_id: int) -> dict[str, Any]:
        tomorrow = date.today() + timedelta(days=1)
        return self.reschedule_visit(visit_id=visit_id, new_date=tomorrow)

# --- API Router moved from app/api/v1/endpoints/visits.py ---

# app/api/v1/endpoints/visits.py

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles

router = APIRouter()


class VisitCreate(BaseModel):
    patient_id: int | None = None
    doctor_id: int | None = None
    notes: str | None = None
    planned_date: date | None = None
    source: str | None = Field(default="desk", max_length=20)


class VisitOut(BaseModel):
    id: int
    patient_id: int | None = None
    doctor_id: int | None = None
    status: str
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    notes: str | None = None
    planned_date: date | None = None
    source: str | None = None


class VisitServiceIn(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    price: float = 0.0
    qty: int = 1


class VisitWithServices(BaseModel):
    visit: VisitOut
    services: list[VisitServiceIn]


@router.get("/visits", response_model=list[VisitOut], summary="Список визитов")
def list_visits(
    patient_id: int | None = Query(default=None),
    doctor_id: int | None = Query(default=None),
    status_q: str | None = Query(default=None),
    planned: date | None = Query(default=None, alias="planned_date"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = VisitsApiService(db).list_visits(
        patient_id=patient_id,
        doctor_id=doctor_id,
        status_q=status_q,
        planned=planned,
        limit=limit,
        offset=offset,
    )
    return [VisitOut(**row) for row in rows]


@router.post(
    "/visits",
    response_model=VisitOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("Admin", "Registrar", "Doctor"))],
    summary="Создать визит",
)
def create_visit(
    request: Request,
    payload: VisitCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    result = VisitsApiService(db).create_visit(
        request=request,
        payload=payload,
        current_user=current_user,
    )
    return VisitOut(**result)


@router.get("/visits/{visit_id}", response_model=VisitWithServices, summary="Карточка визита")
def get_visit(visit_id: int, db: Session = Depends(get_db)):
    payload = VisitsApiService(db).get_visit(visit_id=visit_id)
    return VisitWithServices(
        visit=VisitOut(**payload["visit"]),
        services=[VisitServiceIn(**item) for item in payload["services"]],
    )


@router.post(
    "/visits/{visit_id}/services",
    dependencies=[Depends(require_roles("Admin", "Registrar", "Doctor", "Cashier"))],
    summary="Добавить услугу к визиту",
)
def add_service(visit_id: int, item: VisitServiceIn, db: Session = Depends(get_db)):
    return VisitsApiService(db).add_service(visit_id=visit_id, item=item)


@router.post(
    "/visits/{visit_id}/status",
    dependencies=[Depends(require_roles("Admin", "Doctor", "Registrar"))],
    summary="Смена статуса визита",
)
def set_status(visit_id: int, status_new: str, db: Session = Depends(get_db)):
    visit = VisitsApiService(db).set_status(visit_id=visit_id, status_new=status_new)
    return VisitOut(
        id=visit.id,
        patient_id=visit.patient_id,
        doctor_id=visit.doctor_id,
        status=visit.status,
        created_at=visit.created_at,
        started_at=visit.started_at,
        finished_at=visit.finished_at,
        notes=visit.notes,
        planned_date=visit.visit_date,
    )


@router.post(
    "/visits/{visit_id}/reschedule",
    dependencies=[Depends(require_roles("Admin", "Registrar"))],
    summary="Перенести визит на конкретную дату (new_date в формате YYYY-MM-DD)",
)
def reschedule_visit(
    visit_id: int,
    new_date: date = Query(..., alias="new_date"),
    db: Session = Depends(get_db),
):
    row = VisitsApiService(db).reschedule_visit(visit_id=visit_id, new_date=new_date)
    return VisitOut(**row)


@router.post(
    "/visits/{visit_id}/reschedule/tomorrow",
    dependencies=[Depends(require_roles("Admin", "Registrar"))],
    summary="Перенести визит на завтра (planned_date = today + 1)",
)
def reschedule_visit_tomorrow(visit_id: int, db: Session = Depends(get_db)):
    row = VisitsApiService(db).reschedule_visit_tomorrow(visit_id=visit_id)
    return VisitOut(**row)

