"""Laboratory specimen custody and explicit order/report assignment."""

from __future__ import annotations

import hashlib
import json
import secrets
from collections import defaultdict
from datetime import UTC, datetime
from io import BytesIO

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lab import LabOrder, LabReportInstance
from app.models.lab_specimen import (
    LabSpecimen,
    LabSpecimenAssignment,
    LabSpecimenEvent,
    LabSpecimenRejectionReasonCode,
)
from app.repositories.lab_specimen_repository import SpecimenRepository
from app.schemas.lab_specimen import (
    LabSpecimenAssignmentCommand,
    LabSpecimenCommand,
    LabSpecimenCreate,
    LabSpecimenEventOut,
    LabSpecimenListOut,
    LabSpecimenOut,
    LabSpecimenScan,
    LabSpecimenTargets,
    LabSpecimenTransitionCommand,
    SpecimenAction,
    SpecimenStatus,
)
from app.services.lab_reporting_service import LabReportingDomainError

TRANSITIONS: dict[SpecimenStatus, dict[SpecimenAction, SpecimenStatus]] = {
    "expected": {"collect": "collected", "reject": "rejected"},
    "collected": {"receive": "received", "hold": "held", "reject": "rejected"},
    "received": {"accept": "accepted", "hold": "held", "reject": "rejected"},
    "accepted": {"hold": "held", "reject": "rejected"},
    "held": {"reject": "rejected"},
    "rejected": {},
}


def _status_transitions(specimen: LabSpecimen) -> dict[SpecimenAction, SpecimenStatus]:
    if specimen.status != "held":
        return TRANSITIONS[specimen.status]
    if specimen.received_at is None:
        return {"receive": "received", "reject": "rejected"}
    return {"accept": "accepted", "reject": "rejected"}


def _fingerprint(action: str, command: BaseModel) -> str:
    data = command.model_dump(mode="json", exclude={"request_id"})
    if data.get("reason_code") is None:
        data.pop("reason_code", None)
    for key in ("visit_service_ids", "report_instance_ids"):
        if key in data:
            data[key] = sorted(set(data[key]))
    encoded = json.dumps([action, data], sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _utc(value: datetime | None) -> datetime | None:
    # SQLite strips tzinfo even for timezone-enabled columns in unit tests.
    return (
        value.replace(tzinfo=UTC)
        if value is not None and value.tzinfo is None
        else value
    )


class LabSpecimenService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SpecimenRepository(db)

    def _get_order(self, order_id: int, *, for_update: bool = False) -> LabOrder:
        order = self.repository.get_order(order_id, for_update=for_update)
        if order is None or order.patient_id is None:
            raise LabReportingDomainError(404, "Lab order not found")
        return order

    def _get_locked_specimen(self, specimen_id: int) -> LabSpecimen:
        specimen = self.repository.get(specimen_id, for_update=True)
        if specimen is None:
            raise LabReportingDomainError(404, "Specimen not found")
        return specimen

    def _check_order_editable(self, order: LabOrder) -> None:
        if order.status in {"canceled", "cancelled"}:
            raise LabReportingDomainError(409, "Lab order is canceled")

    def _check_targets(
        self,
        order: LabOrder,
        targets: LabSpecimenTargets,
        reports: list[LabReportInstance],
        *,
        removing_assignment: bool = False,
    ) -> None:
        if set(targets.report_instance_ids) != {report.id for report in reports} or any(
            report.order_id != order.id
            or report.patient_id != order.patient_id
            or report.visit_id != order.visit_id
            for report in reports
        ):
            raise LabReportingDomainError(404, "Report is outside the specimen order")
        if any(report.status not in {"DRAFT", "IN_PROGRESS"} for report in reports):
            raise LabReportingDomainError(
                409, "Report is not open for specimen assignment"
            )
        if targets.visit_service_ids and (
            order.visit_id is None
            or set(targets.visit_service_ids)
            != self.repository.list_visit_service_ids(
                order.visit_id,
                order.patient_id,
                targets.visit_service_ids,
                for_update=True,
            )
        ):
            raise LabReportingDomainError(
                404, "Ordered test is outside the specimen order"
            )
        if (
            targets.visit_service_ids
            and not removing_assignment
            and self.repository.has_visit_service_order_conflict(
                order.id, targets.visit_service_ids
            )
        ):
            raise LabReportingDomainError(
                409, "Ordered test is canceled or belongs to another order"
            )

    def _add_assignments(
        self, specimen: LabSpecimen, targets: LabSpecimenTargets
    ) -> None:
        existing = self.repository.list_assignments([specimen.id])
        existing_services = {row.visit_service_id for row in existing}
        existing_reports = {row.report_instance_id for row in existing}
        self.db.add_all(
            LabSpecimenAssignment(specimen_id=specimen.id, visit_service_id=service_id)
            for service_id in sorted(set(targets.visit_service_ids) - existing_services)
        )
        self.db.add_all(
            LabSpecimenAssignment(specimen_id=specimen.id, report_instance_id=report_id)
            for report_id in sorted(set(targets.report_instance_ids) - existing_reports)
        )

    def _is_replay(
        self,
        specimen: LabSpecimen,
        actor_user_id: int,
        request_id: str,
        fingerprint: str,
    ) -> bool:
        event = self.repository.find_event(specimen.id, request_id)
        if event is None:
            return False
        if (
            event.actor_user_id != actor_user_id
            or event.request_fingerprint != fingerprint
        ):
            raise LabReportingDomainError(409, "Specimen request already used")
        return True

    def _check_revision(
        self, specimen: LabSpecimen, command: LabSpecimenCommand
    ) -> None:
        if specimen.revision != command.expected_revision:
            raise LabReportingDomainError(
                409, "Specimen changed. Refresh and try again"
            )

    def _append_event(
        self,
        specimen: LabSpecimen,
        *,
        action: str,
        actor_user_id: int,
        happened_at: datetime,
        request_id: str,
        fingerprint: str,
        reason: str | None = None,
        reason_code: LabSpecimenRejectionReasonCode | None = None,
        targets: LabSpecimenTargets | None = None,
    ) -> None:
        specimen.revision += 1
        self.db.add(
            LabSpecimenEvent(
                specimen_id=specimen.id,
                revision=specimen.revision,
                action=action,
                resulting_status=specimen.status,
                actor_user_id=actor_user_id,
                happened_at=happened_at,
                reason=reason,
                reason_code=reason_code,
                request_id=request_id,
                request_fingerprint=fingerprint,
                visit_service_ids=sorted(set(targets.visit_service_ids))
                if targets
                else [],
                report_instance_ids=sorted(set(targets.report_instance_ids))
                if targets
                else [],
            )
        )

    def _commit(self) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise LabReportingDomainError(
                409, "Specimen data changed. Refresh and try again"
            ) from exc

    def _finish_mutation(
        self, order: LabOrder, specimen: LabSpecimen
    ) -> LabSpecimenOut:
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise LabReportingDomainError(
                409, "Specimen data changed. Refresh and try again"
            ) from exc
        snapshot = self._outputs(order, [specimen])[0]
        self._commit()
        return snapshot

    def get_list(self, order_id: int) -> tuple[LabSpecimenListOut, int]:
        order = self._get_order(order_id)
        items = self._outputs(order, self.repository.list_for_order(order_id))
        return (
            LabSpecimenListOut(
                items=items, data_status="known" if items else "unknown"
            ),
            order.patient_id,
        )

    def scan(self, query: LabSpecimenScan) -> tuple[LabSpecimenOut, int]:
        specimen = self.repository.find_by_barcode(
            query.barcode.upper(), query.order_id, for_share=True
        )
        if specimen is None:
            raise LabReportingDomainError(404, "Specimen not found")
        order = self._get_order(specimen.order_id)
        return self._outputs(order, [specimen])[0], order.patient_id

    def create_for_visit(
        self, visit_id: int, command: LabSpecimenCreate, actor_user_id: int
    ) -> LabSpecimenOut:
        if not command.visit_service_ids or command.report_instance_ids:
            raise LabReportingDomainError(
                422, "Explicit ordered laboratory tests are required"
            )
        # Existing report creation takes this same visit lock before looking up
        # an implicit order. It serializes first collection with first report.
        visit = self.repository.get_visit_for_collection(visit_id)
        if visit is None or visit.patient_id is None:
            raise LabReportingDomainError(404, "Visit not found")
        if set(command.visit_service_ids) != self.repository.list_visit_service_ids(
            visit.id, visit.patient_id, command.visit_service_ids
        ):
            raise LabReportingDomainError(
                404, "Ordered test is outside the specimen visit"
            )

        orders = self.repository.list_visit_orders(visit.id, visit.patient_id)
        if len(orders) > 1:
            raise LabReportingDomainError(
                409, "Multiple laboratory orders. Select the specific order"
            )
        if orders:
            order = orders[0]
        else:
            if (
                command.parent_specimen_id is not None
                or command.replaces_specimen_id is not None
            ):
                raise LabReportingDomainError(404, "Specimen not found")
            order = LabOrder(
                visit_id=visit.id, patient_id=visit.patient_id, status="ordered"
            )
            self.db.add(order)
            self.db.flush()
        return self.create(order.id, command, actor_user_id)

    def create(
        self, order_id: int, command: LabSpecimenCreate, actor_user_id: int
    ) -> LabSpecimenOut:
        request_id = str(command.request_id)
        fingerprint = _fingerprint("create", command)
        # Specimen mutations and release share report-first locking.
        reports = self.repository.lock_reports(command.report_instance_ids)
        order = self._get_order(order_id, for_update=True)
        existing = self.repository.find_create_request(order_id, request_id)
        if existing is not None and self._is_replay(
            existing, actor_user_id, request_id, fingerprint
        ):
            return self._outputs(order, [existing])[0]

        self._check_order_editable(order)
        origin_id = command.parent_specimen_id or command.replaces_specimen_id
        action = "create"
        if origin_id is not None:
            origin = self._get_locked_specimen(origin_id)
            if origin.order_id != order.id:
                raise LabReportingDomainError(404, "Specimen not found")
            if origin.material_code != command.material_code:
                raise LabReportingDomainError(
                    409, "Specimen material must match its source"
                )
            if command.parent_specimen_id is not None:
                if origin.status != "accepted":
                    raise LabReportingDomainError(
                        409, "Aliquot source must be accepted"
                    )
                action = "aliquot"
            else:
                if origin.status != "rejected" or self.repository.replacement_exists(
                    origin.id
                ):
                    raise LabReportingDomainError(409, "Specimen cannot be recollected")
                action = "recollect"

        # Mutations sharing a specimen lock it before their visit-service
        # rows. This also keeps recollection and assignment lock order aligned.
        self._check_targets(order, command, reports)
        now = datetime.now(UTC)
        specimen = LabSpecimen(
            order_id=order.id,
            barcode=f"SP-{secrets.token_hex(8).upper()}",
            material_code=command.material_code,
            container_code=command.container_code,
            status="expected",
            revision=1,
            parent_specimen_id=command.parent_specimen_id,
            replaces_specimen_id=command.replaces_specimen_id,
            create_request_id=request_id,
            created_at=now,
        )
        self.db.add(specimen)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise LabReportingDomainError(
                409, "Specimen data changed. Refresh and try again"
            ) from exc
        self._add_assignments(specimen, command)
        self.db.add(
            LabSpecimenEvent(
                specimen_id=specimen.id,
                revision=1,
                action=action,
                resulting_status=specimen.status,
                actor_user_id=actor_user_id,
                happened_at=now,
                request_id=request_id,
                request_fingerprint=fingerprint,
                visit_service_ids=sorted(set(command.visit_service_ids)),
                report_instance_ids=sorted(set(command.report_instance_ids)),
            )
        )
        return self._finish_mutation(order, specimen)

    def transition(
        self,
        specimen_id: int,
        command: LabSpecimenTransitionCommand,
        actor_user_id: int,
    ) -> LabSpecimenOut:
        specimen = self._get_locked_specimen(specimen_id)
        order = self._get_order(specimen.order_id)
        request_id = str(command.request_id)
        fingerprint = _fingerprint(command.action, command)
        if self._is_replay(specimen, actor_user_id, request_id, fingerprint):
            return self._outputs(order, [specimen])[0]

        self._check_order_editable(order)
        self._check_revision(specimen, command)
        new_status = _status_transitions(specimen).get(command.action)
        if new_status is None:
            raise LabReportingDomainError(409, "Specimen transition is not available")
        now = datetime.now(UTC)
        specimen.status = new_status
        specimen.latest_reason = (
            command.reason if new_status in {"held", "rejected"} else None
        )
        match command.action:
            case "collect":
                specimen.collected_at = now
            case "receive":
                specimen.received_at = now
            case "accept":
                specimen.accepted_at = now

        self._append_event(
            specimen,
            action=command.action,
            actor_user_id=actor_user_id,
            happened_at=now,
            request_id=request_id,
            fingerprint=fingerprint,
            reason=command.reason,
            reason_code=command.reason_code,
        )
        return self._finish_mutation(order, specimen)

    def _remove_assignments(
        self, specimen: LabSpecimen, targets: LabSpecimenTargets
    ) -> None:
        existing = self.repository.list_assignments([specimen.id])
        visit_service_ids = set(targets.visit_service_ids)
        report_instance_ids = set(targets.report_instance_ids)
        to_remove = [
            row
            for row in existing
            if row.visit_service_id in visit_service_ids
            or row.report_instance_id in report_instance_ids
        ]
        if len(to_remove) != len(visit_service_ids) + len(report_instance_ids):
            raise LabReportingDomainError(
                409, "Specimen assignment is no longer present"
            )
        for row in to_remove:
            self.db.delete(row)

    def assign(
        self,
        specimen_id: int,
        command: LabSpecimenAssignmentCommand,
        actor_user_id: int,
    ) -> LabSpecimenOut:
        reports = self.repository.lock_reports(command.report_instance_ids)
        specimen = self._get_locked_specimen(specimen_id)
        order = self._get_order(specimen.order_id)
        request_id = str(command.request_id)
        action = "unassign" if command.operation == "remove" else "assign"
        fingerprint = _fingerprint(action, command)
        if self._is_replay(specimen, actor_user_id, request_id, fingerprint):
            return self._outputs(order, [specimen])[0]

        self._check_order_editable(order)
        self._check_revision(specimen, command)
        self._check_targets(
            order, command, reports, removing_assignment=command.operation == "remove"
        )
        if command.operation == "remove":
            self._remove_assignments(specimen, command)
        else:
            if specimen.status == "rejected":
                raise LabReportingDomainError(
                    409, "Rejected specimen cannot be assigned"
                )
            self._add_assignments(specimen, command)
        self._append_event(
            specimen,
            action=action,
            actor_user_id=actor_user_id,
            happened_at=datetime.now(UTC),
            request_id=request_id,
            fingerprint=fingerprint,
            reason=command.reason,
            targets=command,
        )
        return self._finish_mutation(order, specimen)

    def issue_label(
        self, specimen_id: int, command: LabSpecimenCommand, actor_user_id: int
    ) -> bytes:
        specimen = self._get_locked_specimen(specimen_id)
        order = self._get_order(specimen.order_id)
        request_id = str(command.request_id)
        fingerprint = _fingerprint("print_label", command)
        replayed = self._is_replay(specimen, actor_user_id, request_id, fingerprint)
        if not replayed:
            self._check_order_editable(order)
            self._check_revision(specimen, command)
            if specimen.status == "rejected":
                raise LabReportingDomainError(
                    409, "Rejected specimen cannot be labeled"
                )
        # Render before committing that the label was issued.
        pdf = _render_label(specimen)
        if not replayed:
            self._append_event(
                specimen,
                action="print_label",
                actor_user_id=actor_user_id,
                happened_at=datetime.now(UTC),
                request_id=request_id,
                fingerprint=fingerprint,
            )
            self._commit()
        return pdf

    def _outputs(
        self, order: LabOrder, specimens: list[LabSpecimen]
    ) -> list[LabSpecimenOut]:
        if not specimens:
            return []
        service_ids: dict[int, list[int]] = defaultdict(list)
        report_ids: dict[int, list[int]] = defaultdict(list)
        events: dict[int, list[LabSpecimenEventOut]] = defaultdict(list)
        ids = [specimen.id for specimen in specimens]
        for row in self.repository.list_assignments(ids):
            if row.visit_service_id is not None:
                service_ids[row.specimen_id].append(row.visit_service_id)
            if row.report_instance_id is not None:
                report_ids[row.specimen_id].append(row.report_instance_id)
        for row in self.repository.list_events(ids):
            events[row.specimen_id].append(
                LabSpecimenEventOut.model_validate(row).model_copy(
                    update={"happened_at": _utc(row.happened_at)}
                )
            )
        replaced = self.repository.replaced_ids(ids)
        editable = order.status not in {"canceled", "cancelled"}
        output: list[LabSpecimenOut] = []
        for specimen in specimens:
            actions: list[SpecimenAction] = []
            if editable:
                actions.extend(_status_transitions(specimen))
                if specimen.status != "rejected":
                    actions.extend(["assign", "print_label"])
                if specimen.status == "accepted":
                    actions.append("aliquot")
                if specimen.status == "rejected" and specimen.id not in replaced:
                    actions.append("recollect")
            output.append(
                LabSpecimenOut(
                    id=specimen.id,
                    order_id=specimen.order_id,
                    visit_id=order.visit_id,
                    barcode=specimen.barcode,
                    material_code=specimen.material_code,
                    container_code=specimen.container_code,
                    status=specimen.status,
                    revision=specimen.revision,
                    created_at=_utc(specimen.created_at),
                    collected_at=_utc(specimen.collected_at),
                    received_at=_utc(specimen.received_at),
                    accepted_at=_utc(specimen.accepted_at),
                    latest_reason=specimen.latest_reason,
                    parent_specimen_id=specimen.parent_specimen_id,
                    replaces_specimen_id=specimen.replaces_specimen_id,
                    visit_service_ids=service_ids[specimen.id],
                    report_instance_ids=report_ids[specimen.id],
                    available_actions=actions,
                    events=events[specimen.id],
                )
            )
        return output


def _render_label(specimen: LabSpecimen) -> bytes:
    from reportlab.graphics.barcode.code128 import Code128
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas

    buffer = BytesIO()
    page_width = 100 * mm
    canvas = Canvas(buffer, pagesize=(page_width, 40 * mm), invariant=True)
    canvas.setTitle("Specimen label")
    barcode = Code128(specimen.barcode, barWidth=0.28 * mm, barHeight=14 * mm)
    barcode.drawOn(canvas, (page_width - barcode.width) / 2, 17 * mm)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawCentredString(page_width / 2, 12 * mm, specimen.barcode)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(
        page_width / 2, 8.5 * mm, f"Specimen {specimen.id} / Order {specimen.order_id}"
    )
    # Each allowed 32-character code fits on its own line.
    canvas.setFont("Helvetica", 6)
    canvas.drawCentredString(page_width / 2, 5.25 * mm, specimen.material_code)
    canvas.drawCentredString(page_width / 2, 2 * mm, specimen.container_code)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()
