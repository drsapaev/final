from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.lab import LabOrder, LabReportInstance
from app.models.lab_specimen import LabSpecimen, LabSpecimenAssignment, LabSpecimenEvent
from app.models.visit import Visit, VisitService
from app.repositories.lab_ordered_test_repository import lab_visit_services


class SpecimenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_order(self, order_id: int, *, for_update: bool = False) -> LabOrder | None:
        query = select(LabOrder).where(LabOrder.id == order_id)
        if for_update:
            query = query.with_for_update(key_share=True).execution_options(
                populate_existing=True
            )
        return self.db.scalar(query)

    def get_visit_for_collection(self, visit_id: int) -> Visit | None:
        return self.db.scalar(
            select(Visit).where(Visit.id == visit_id).with_for_update(key_share=True)
        )

    def list_visit_orders(self, visit_id: int, patient_id: int) -> list[LabOrder]:
        return list(
            self.db.scalars(
                select(LabOrder)
                .where(
                    LabOrder.visit_id == visit_id,
                    LabOrder.patient_id == patient_id,
                    LabOrder.status.not_in(("canceled", "cancelled")),
                )
                .order_by(LabOrder.id)
                .limit(2)
            )
        )

    def get(self, specimen_id: int, *, for_update: bool = False) -> LabSpecimen | None:
        query = select(LabSpecimen).where(LabSpecimen.id == specimen_id)
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(query)

    def find_by_barcode(
        self, barcode: str, order_id: int | None, *, for_share: bool = False
    ) -> LabSpecimen | None:
        query = select(LabSpecimen).where(LabSpecimen.barcode == barcode)
        if order_id is not None:
            query = query.where(LabSpecimen.order_id == order_id)
        if for_share:
            query = query.with_for_update(read=True).execution_options(
                populate_existing=True
            )
        return self.db.scalar(query)

    def find_create_request(self, order_id: int, request_id: str) -> LabSpecimen | None:
        return self.db.scalar(
            select(LabSpecimen)
            .where(
                LabSpecimen.order_id == order_id,
                LabSpecimen.create_request_id == request_id,
            )
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )

    def find_event(self, specimen_id: int, request_id: str) -> LabSpecimenEvent | None:
        return self.db.scalar(
            select(LabSpecimenEvent).where(
                LabSpecimenEvent.specimen_id == specimen_id,
                LabSpecimenEvent.request_id == request_id,
            )
        )

    def list_for_order(self, order_id: int) -> list[LabSpecimen]:
        # Keep the specimen rows stable while their events and assignments
        # are projected. All mutations lock their specimen before writing.
        return list(
            self.db.scalars(
                select(LabSpecimen)
                .where(LabSpecimen.order_id == order_id)
                .order_by(LabSpecimen.id)
                .with_for_update(read=True)
                .execution_options(populate_existing=True)
            )
        )

    def _report_specimen_ids(self, report_id: int) -> Select:
        return select(LabSpecimenAssignment.specimen_id).where(
            LabSpecimenAssignment.report_instance_id == report_id,
        )

    def _active_report_specimens(self, report_id: int) -> Select:
        assigned = self._report_specimen_ids(report_id)
        # Only an explicitly assigned recollection supersedes a rejected sample
        # for this report. An unrelated recollection cannot release the report.
        replaced = (
            select(LabSpecimen.replaces_specimen_id)
            .where(
                LabSpecimen.id.in_(assigned),
                LabSpecimen.replaces_specimen_id.is_not(None),
            )
            .correlate(None)
        )
        return select(LabSpecimen).where(
            LabSpecimen.id.in_(assigned), LabSpecimen.id.not_in(replaced)
        )

    def list_for_report(
        self, report_id: int, *, for_update: bool = False
    ) -> list[LabSpecimen]:
        query = self._active_report_specimens(report_id).order_by(LabSpecimen.id)
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        return list(self.db.scalars(query))

    def list_for_release(
        self, report_id: int, *, for_update: bool = True
    ) -> list[LabSpecimen]:
        """Read report specimens and aliquot sources in canonical id order."""
        ancestry = (
            self._active_report_specimens(report_id)
            .with_only_columns(LabSpecimen.id, LabSpecimen.parent_specimen_id)
            .cte("lab_specimen_ancestry", recursive=True)
        )
        ancestry = ancestry.union(
            select(LabSpecimen.id, LabSpecimen.parent_specimen_id).join(
                ancestry, LabSpecimen.id == ancestry.c.parent_specimen_id
            )
        )
        query = (
            select(LabSpecimen)
            .where(LabSpecimen.id.in_(select(ancestry.c.id)))
            .order_by(LabSpecimen.id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            query = query.with_for_update()
        return list(self.db.scalars(query))

    def replacement_exists(self, specimen_id: int) -> bool:
        return specimen_id in self.replaced_ids([specimen_id])

    def replaced_ids(self, specimen_ids: list[int]) -> set[int]:
        return set(
            self.db.scalars(
                select(LabSpecimen.replaces_specimen_id).where(
                    LabSpecimen.replaces_specimen_id.in_(specimen_ids)
                )
            )
        )

    def lock_reports(self, report_ids: list[int]) -> list[LabReportInstance]:
        if not report_ids:
            return []
        return list(
            self.db.scalars(
                select(LabReportInstance)
                .where(LabReportInstance.id.in_(report_ids))
                .order_by(LabReportInstance.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def list_visit_service_ids(self, visit_id: int, service_ids: list[int]) -> set[int]:
        return set(
            self.db.scalars(
                lab_visit_services().where(
                    VisitService.visit_id == visit_id,
                    VisitService.id.in_(service_ids),
                )
            )
        )

    def list_assignments(self, specimen_ids: list[int]) -> list[LabSpecimenAssignment]:
        return list(
            self.db.scalars(
                select(LabSpecimenAssignment)
                .where(LabSpecimenAssignment.specimen_id.in_(specimen_ids))
                .order_by(LabSpecimenAssignment.specimen_id, LabSpecimenAssignment.id)
            )
        )

    def list_events(self, specimen_ids: list[int]) -> list[LabSpecimenEvent]:
        return list(
            self.db.scalars(
                select(LabSpecimenEvent)
                .where(LabSpecimenEvent.specimen_id.in_(specimen_ids))
                .order_by(LabSpecimenEvent.specimen_id, LabSpecimenEvent.revision)
            )
        )
