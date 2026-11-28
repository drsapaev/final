"""Review and quality-control decisions for managed lab reports."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.crud import audit as audit_crud
from app.models.audit import AuditLog
from app.models.lab import (
    FINAL_INSTANCE_STATUSES,
    LabClinicalConfigurationVersion,
    LabOrderTest,
    LabReportInstance,
)
from app.models.lab_release import LabReportWorkflowEvent
from app.models.lab_specimen import LabSpecimen
from app.models.role_permission import Permission
from app.models.user import User
from app.models.visit import VisitService
from app.repositories.lab_specimen_repository import SpecimenRepository
from app.schemas.lab_release import LabReportQCIn
from app.services.authorization.staff import staff_authorization_service
from app.services.group_permissions_service import get_group_permissions_service
from app.services.lab_reporting._base import (
    LabReportingDomainError,
    LabReportingServiceMixinBase,
)
from app.services.service_mapping import normalize_service_code

_MANAGED_DRAFT_STATUSES = {"DRAFT", "IN_PROGRESS"}
_WORKFLOW_PERMISSIONS = {"lab:review", "lab:release", "lab:qc"}
MANUAL_REVIEW_HOLDS = frozenset({"instrument_warning", "unusual_change"})
_DRAFT_EDIT_AUDIT_ACTION = "LAB_REPORT_DRAFT_EDITED"
_REPORT_AUDIT_ENTITY = "lab_report"


class WorkflowMixin(LabReportingServiceMixinBase):
    def _workflow_actor(self, actor_user_id: int | None) -> User:
        actor = self.db.get(User, actor_user_id) if actor_user_id is not None else None
        if (
            not actor
            or not actor.is_active
            or not staff_authorization_service.can_write_lab(actor)
        ):
            raise LabReportingDomainError(403, "Laboratory workflow access denied")
        return actor

    def _workflow_permissions(self, actor: User) -> set[str]:
        granted = (
            get_group_permissions_service().get_user_permissions(
                self.db,
                actor.id,
                use_cache=False,
            )
            & _WORKFLOW_PERMISSIONS
        )
        if not granted:
            return set()
        return set(
            self.db.scalars(
                select(Permission.codename).where(
                    Permission.codename.in_(granted),
                    Permission.is_active.is_(True),
                )
            )
        )

    def _require_workflow_permission(self, actor: User, permission: str) -> None:
        if permission not in self._workflow_permissions(actor):
            raise LabReportingDomainError(
                403, "Laboratory workflow permission required"
            )

    def _require_assigned_clinical_reviewer(
        self, instance: LabReportInstance, actor: User
    ) -> None:
        """Require the pinned clinic's assigned Lab physician for clinical sign-off.

        A report keeps the authority assignments from the configuration version
        it was created with, even after that version is archived. Managed reports
        without an approved, pinned configuration cannot be reviewed or released.
        """
        configuration_id = instance.clinical_configuration_version_id
        if configuration_id is None:
            raise LabReportingDomainError(
                409, "Approved clinic clinical configuration required for sign-off"
            )
        configuration = self.db.get(LabClinicalConfigurationVersion, configuration_id)
        if (
            configuration is None
            or configuration.status not in {"APPROVED", "ARCHIVED"}
            or configuration.approved_at is None
            or configuration.primary_lab_physician_user_id is None
        ):
            raise LabReportingDomainError(
                409, "Pinned clinical configuration is unavailable for sign-off"
            )
        assigned_ids = {
            configuration.primary_lab_physician_user_id,
            configuration.substitute_lab_physician_user_id,
        }
        if (
            not actor.is_active
            or actor.role != "Lab"
            or actor.id not in assigned_ids
        ):
            raise LabReportingDomainError(
                403, "Assigned active laboratory physician required for clinical sign-off"
            )

    def _can_sign_off_clinically(
        self, instance: LabReportInstance, actor: User
    ) -> bool:
        try:
            self._require_assigned_clinical_reviewer(instance, actor)
        except LabReportingDomainError:
            return False
        return True

    def _assert_instance_mutable_draft(self, instance: LabReportInstance) -> None:
        self._assert_instance_editable(instance)
        if instance.managed_release and instance.status not in _MANAGED_DRAFT_STATUSES:
            raise LabReportingDomainError(
                409, "Return the report to draft before editing"
            )

    @staticmethod
    def _workflow_expected_version(expected_updated_at: str | None) -> datetime:
        if expected_updated_at is None:
            raise LabReportingDomainError(400, "Expected report version is required")
        try:
            if len(expected_updated_at) < 19:
                raise ValueError
            value = datetime.fromisoformat(expected_updated_at.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise LabReportingDomainError(400, "Invalid report version") from exc
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )

    def _append_workflow_event(
        self,
        instance: LabReportInstance,
        *,
        kind: str,
        actor: User,
        expected_version: datetime | None = None,
        reason: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            LabReportWorkflowEvent(
                instance_id=instance.id,
                kind=kind,
                actor_user_id=actor.id,
                actor_name=(actor.full_name or actor.username)[:255],
                occurred_at=datetime.now(UTC),
                report_version=instance.updated_at,
                expected_version=expected_version,
                reason=reason,
                evidence=evidence,
            )
        )

    def _record_report_draft_edit(
        self,
        instance: LabReportInstance,
        actor: User,
    ) -> None:
        audit_crud.log(
            self.db,
            action=_DRAFT_EDIT_AUDIT_ACTION,
            entity_type=_REPORT_AUDIT_ENTITY,
            entity_id=instance.id,
            actor_user_id=actor.id,
        )

    def workflow_history(self, instance_id: int) -> list[LabReportWorkflowEvent]:
        return list(
            self.db.scalars(
                select(LabReportWorkflowEvent)
                .where(
                    LabReportWorkflowEvent.instance_id == instance_id,
                )
                .order_by(LabReportWorkflowEvent.id)
            )
        )

    def _latest_workflow_event(
        self,
        instance_id: int,
        kind: str,
    ) -> LabReportWorkflowEvent | None:
        return self.db.scalar(
            select(LabReportWorkflowEvent)
            .where(
                LabReportWorkflowEvent.instance_id == instance_id,
                LabReportWorkflowEvent.kind == kind,
            )
            .order_by(LabReportWorkflowEvent.id.desc())
            .limit(1)
        )

    def _workflow_request_replayed(
        self,
        instance: LabReportInstance,
        *,
        kind: str,
        actor: User,
        expected_version: datetime,
        reason: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> bool:
        event = self._latest_workflow_event(instance.id, kind)
        return bool(
            event
            and event.actor_user_id == actor.id
            and event.expected_version
            and self._normalized_version(event.expected_version) == expected_version
            and self._normalized_version(event.report_version)
            == self._normalized_version(instance.updated_at)
            and event.reason == reason
            and (evidence is None or event.evidence == evidence)
        )

    def _reviewer_has_separation(self, instance_id: int, actor: User) -> bool:
        if not settings.LAB_RELEASE_REQUIRE_DISTINCT_REVIEWER:
            return True
        authorship = self.db.scalar(
            select(LabReportWorkflowEvent.id)
            .where(
                LabReportWorkflowEvent.instance_id == instance_id,
                LabReportWorkflowEvent.kind.in_(
                    ("entered", "submitted", "revision_created")
                ),
                LabReportWorkflowEvent.actor_user_id == actor.id,
            )
            .limit(1)
        )
        if authorship is not None:
            return False
        draft_edit = self.db.scalar(
            select(AuditLog.id)
            .where(
                AuditLog.action == _DRAFT_EDIT_AUDIT_ACTION,
                AuditLog.entity_type == _REPORT_AUDIT_ENTITY,
                AuditLog.entity_id == instance_id,
                AuditLog.actor_user_id == actor.id,
            )
            .limit(1)
        )
        return draft_edit is None

    def managed_workflow_actions(
        self,
        instance: LabReportInstance,
        actor_user_id: int | None,
    ) -> list[str]:
        try:
            actor = self._workflow_actor(actor_user_id)
        except LabReportingDomainError:
            return []
        if instance.status in FINAL_INSTANCE_STATUSES:
            return ["revise", "print"]
        permissions = self._workflow_permissions(actor)
        actions = ["preview"]
        if instance.status in _MANAGED_DRAFT_STATUSES:
            actions.extend(["edit", "save_draft", "submit_review"])
            if "lab:qc" in permissions:
                actions.append("record_qc")
        if instance.status in {"IN_REVIEW", "REVIEWED"} and "lab:review" in permissions:
            actions.append("return_to_draft")
            if (
                instance.status == "IN_REVIEW"
                and self._can_sign_off_clinically(instance, actor)
                and self._reviewer_has_separation(instance.id, actor)
            ):
                actions.append("review")
        if (
            instance.status == "REVIEWED"
            and "lab:release" in permissions
            and self._can_sign_off_clinically(instance, actor)
            and self._reviewer_has_separation(instance.id, actor)
        ):
            actions.append("finalize")
        return actions

    def _release_prerequisites(
        self,
        instance: LabReportInstance,
        *,
        lock_specimens: bool,
    ) -> tuple[list[str], dict[str, Any]]:
        holds = []
        if instance.clinical_configuration_version_id is None:
            holds.append("clinical_configuration_required")
        if not self._has_published_template(instance):
            holds.append("published_template_required")

        specimens = SpecimenRepository(self.db).list_for_release(
            instance.id, for_update=lock_specimens
        )
        if not specimens:
            holds.append("specimen_required")
        elif any(specimen.status != "accepted" for specimen in specimens):
            holds.append("specimen_not_accepted")
        if len({specimen.material_code for specimen in specimens}) > 1:
            holds.append("specimen_context_ambiguous")
        if instance.values:
            eligible_ids = self._accepted_result_specimen_ids(
                instance, specimens=specimens
            )
            for value in instance.values:
                result = value.result_payload or {}
                has_measurement = value.value_numeric is not None or bool(
                    value.value_text and value.value_text.strip()
                )
                if (
                    has_measurement
                    and result.get("kind") != "absent"
                    and result.get("source_specimen_id") not in eligible_ids
                ):
                    holds.append("specimen_result_mismatch")
                    break

        qc = self._latest_workflow_event(instance.id, "qc_recorded")
        if qc is None:
            holds.append("qc_missing")
        elif (qc.evidence or {}).get("qc", {}).get("status") not in {
            "accepted",
            "not_applicable",
        }:
            holds.append("qc_rejected")

        evidence = {
            "specimens": [
                {"id": item.id, "status": item.status, "revision": item.revision}
                for item in specimens
            ],
            "qc_event_id": qc.id if qc else None,
        }
        return holds, evidence

    def _accepted_result_specimen_ids(
        self,
        instance: LabReportInstance,
        *,
        specimens: list[LabSpecimen] | None = None,
    ) -> set[int]:
        repository = SpecimenRepository(self.db)
        if specimens is None:
            specimens = repository.list_for_release(instance.id)
        directly_assigned = {
            item.id for item in repository.list_for_report(instance.id)
        }
        return {
            item.id
            for item in specimens
            if item.id in directly_assigned
            and item.order_id == instance.order_id
            and item.status == "accepted"
        }

    @staticmethod
    def _has_published_template(instance: LabReportInstance) -> bool:
        version = instance.template_version
        return (
            version.status in {"PUBLISHED", "ARCHIVED"}
            and version.published_at is not None
        )

    def report_release_holds(self, instance: LabReportInstance) -> list[str]:
        if not instance.managed_release or instance.status in FINAL_INSTANCE_STATUSES:
            return []
        holds, evidence = self._release_prerequisites(instance, lock_specimens=False)
        if instance.status in {"IN_REVIEW", "REVIEWED"}:
            event_kind = "submitted" if instance.status == "IN_REVIEW" else "reviewed"
            event = self._latest_workflow_event(instance.id, event_kind)
            if (
                not event
                or self._normalized_version(event.report_version)
                != self._normalized_version(instance.updated_at)
                or event.evidence != evidence
            ):
                holds.append("review_evidence_changed")
        if instance.status in _MANAGED_DRAFT_STATUSES or instance.status == "IN_REVIEW":
            holds.extend(self._manual_review_holds(instance))
        return holds

    def _has_unresolved_unusual_change(self, instance_id: int) -> bool:
        returned = self._latest_workflow_event(instance_id, "returned")
        if returned is None or not (returned.evidence or {}).get("unusual_change"):
            return False
        reviewed = self._latest_workflow_event(instance_id, "reviewed")
        return reviewed is None or reviewed.id < returned.id

    def _manual_review_holds(self, instance: LabReportInstance) -> list[str]:
        holds = []
        for value in instance.values:
            if (value.evaluation_snapshot or {}).get("visible") is False:
                continue
            origin = (value.result_payload or {}).get("import_origin")
            if isinstance(origin, dict) and origin.get("instrument_flags"):
                holds.append("instrument_warning")
                break
        if self._has_unresolved_unusual_change(instance.id):
            holds.append("unusual_change")
        return holds

    def _assert_managed_prerequisites(
        self, instance: LabReportInstance
    ) -> dict[str, Any]:
        holds, evidence = self._release_prerequisites(instance, lock_specimens=True)
        if holds:
            raise LabReportingDomainError(409, ", ".join(holds))
        return evidence

    def submit_for_review(
        self,
        instance_id: int,
        *,
        actor_user_id: int,
        expected_updated_at: str,
    ) -> LabReportInstance:
        actor = self._workflow_actor(actor_user_id)
        instance = self._get_locked_instance(instance_id)
        expected_version = self._workflow_expected_version(expected_updated_at)
        if self._workflow_request_replayed(
            instance,
            kind="submitted",
            actor=actor,
            expected_version=expected_version,
        ):
            return instance
        if (
            not instance.managed_release
            or instance.status not in _MANAGED_DRAFT_STATUSES
        ):
            raise LabReportingDomainError(
                409, "Only managed drafts can be submitted for review"
            )
        self._assert_not_concurrently_modified(instance, expected_updated_at)
        if not self._has_published_template(instance):
            raise LabReportingDomainError(
                409, "Review requires a published template version"
            )
        holds, evidence = self._release_prerequisites(instance, lock_specimens=True)
        if "specimen_result_mismatch" in holds:
            raise LabReportingDomainError(409, "specimen_result_mismatch")
        values, context = self._refresh_result_evaluation(
            instance, validate_existing=True
        )
        self._assert_required_results(instance, values, context)
        instance.status = "IN_REVIEW"
        self._advance_instance_version(instance)
        self._append_workflow_event(
            instance,
            kind="submitted",
            actor=actor,
            expected_version=expected_version,
            evidence=evidence,
        )
        self.repository.commit()
        return self.get_instance(instance.id)

    def review_report(
        self,
        instance_id: int,
        *,
        actor_user_id: int,
        expected_updated_at: str,
        reason: str | None = None,
    ) -> LabReportInstance:
        actor = self._workflow_actor(actor_user_id)
        self._require_workflow_permission(actor, "lab:review")
        instance = self._get_locked_instance(instance_id)
        self._require_assigned_clinical_reviewer(instance, actor)
        expected_version = self._workflow_expected_version(expected_updated_at)
        reason = self._workflow_reason(reason) if reason is not None else None
        if self._workflow_request_replayed(
            instance,
            kind="reviewed",
            actor=actor,
            expected_version=expected_version,
            reason=reason,
        ):
            return instance
        if not instance.managed_release or instance.status != "IN_REVIEW":
            raise LabReportingDomainError(409, "Report must be submitted for review")
        self._assert_not_concurrently_modified(instance, expected_updated_at)
        if not self._reviewer_has_separation(instance.id, actor):
            raise LabReportingDomainError(
                403, "Report requires a reviewer who did not enter it"
            )
        evidence = self._assert_managed_prerequisites(instance)
        submission = self._latest_workflow_event(instance.id, "submitted")
        if (
            not submission
            or self._normalized_version(submission.report_version)
            != self._normalized_version(instance.updated_at)
            or submission.evidence != evidence
        ):
            raise LabReportingDomainError(
                409, "Report evidence changed after submission"
            )
        if reason is None:
            manual_holds = self._manual_review_holds(instance)
            if manual_holds:
                raise LabReportingDomainError(409, ", ".join(manual_holds))
        instance.status = "REVIEWED"
        self._advance_instance_version(instance)
        self._append_workflow_event(
            instance,
            kind="reviewed",
            actor=actor,
            expected_version=expected_version,
            reason=reason,
            evidence=evidence,
        )
        self.repository.commit()
        return self.get_instance(instance.id)

    def return_report_to_draft(
        self,
        instance_id: int,
        *,
        actor_user_id: int,
        expected_updated_at: str,
        reason: str,
        unusual_change: bool = False,
    ) -> LabReportInstance:
        actor = self._workflow_actor(actor_user_id)
        self._require_workflow_permission(actor, "lab:review")
        instance = self._get_locked_instance(instance_id)
        expected_version = self._workflow_expected_version(expected_updated_at)
        reason = self._workflow_reason(reason)
        evidence = None
        if unusual_change or self._has_unresolved_unusual_change(instance.id):
            evidence = {"unusual_change": True}
        if self._workflow_request_replayed(
            instance,
            kind="returned",
            actor=actor,
            expected_version=expected_version,
            reason=reason,
            evidence=evidence,
        ):
            return instance
        if not instance.managed_release or instance.status not in {
            "IN_REVIEW",
            "REVIEWED",
        }:
            raise LabReportingDomainError(
                409, "Only reports in review can return to draft"
            )
        self._assert_not_concurrently_modified(instance, expected_updated_at)
        instance.status = "IN_PROGRESS"
        self._advance_instance_version(instance)
        self._append_workflow_event(
            instance,
            kind="returned",
            actor=actor,
            expected_version=expected_version,
            reason=reason,
            evidence=evidence,
        )
        self.repository.commit()
        return self.get_instance(instance.id)

    @staticmethod
    def _workflow_reason(reason: str | None) -> str:
        normalized = (reason or "").strip()
        if not normalized or len(normalized) > 1000:
            raise LabReportingDomainError(
                400, "Provide a reason between 1 and 1000 characters"
            )
        return normalized

    def record_report_qc(
        self,
        instance_id: int,
        *,
        actor_user_id: int,
        command: LabReportQCIn,
    ) -> LabReportInstance:
        actor = self._workflow_actor(actor_user_id)
        self._require_workflow_permission(actor, "lab:qc")
        instance = self._get_locked_instance(instance_id)
        expected_version = self._workflow_expected_version(command.expected_updated_at)
        evidence = {
            "qc": command.model_dump(
                exclude={"expected_updated_at", "reason"}, mode="json"
            )
        }
        if self._workflow_request_replayed(
            instance,
            kind="qc_recorded",
            actor=actor,
            expected_version=expected_version,
            reason=command.reason,
            evidence=evidence,
        ):
            return instance
        if not instance.managed_release:
            raise LabReportingDomainError(
                409, "QC disposition requires managed release"
            )
        self._assert_instance_mutable_draft(instance)
        self._assert_not_concurrently_modified(instance, command.expected_updated_at)
        self._advance_instance_version(instance)
        self._append_workflow_event(
            instance,
            kind="qc_recorded",
            actor=actor,
            expected_version=expected_version,
            reason=command.reason,
            evidence=evidence,
        )
        self.repository.commit()
        return self.get_instance(instance.id)

    def _claim_ordered_services(
        self,
        instance: LabReportInstance,
        visit_service_ids: list[int],
        template_code: str,
    ) -> None:
        if not visit_service_ids:
            if instance.managed_release and instance.visit_id:
                raise LabReportingDomainError(
                    400, "Select at least one ordered laboratory service"
                )
            return
        if not instance.visit_id or not instance.order_id:
            raise LabReportingDomainError(
                400, "Ordered services require a visit and lab order"
            )
        if (
            instance.order is None
            or instance.order.patient_id != instance.patient_id
            or instance.order.visit_id != instance.visit_id
        ):
            raise LabReportingDomainError(
                409, "Ordered service requires the same patient and visit"
            )
        selected_ids = set(visit_service_ids)
        rows = list(
            self.db.scalars(
                select(VisitService)
                .where(
                    VisitService.id.in_(selected_ids),
                    VisitService.visit_id == instance.visit_id,
                )
                .order_by(VisitService.id)
                .with_for_update()
            )
        )
        if len(rows) != len(selected_ids):
            raise LabReportingDomainError(
                409, "Ordered service does not belong to the report visit"
            )
        if (
            self.db.scalar(
                select(LabOrderTest.id)
                .where(
                    LabOrderTest.visit_service_id.in_(selected_ids),
                )
                .limit(1)
            )
            is not None
        ):
            raise LabReportingDomainError(
                409, "Ordered service has already been allocated or canceled"
            )

        from app.repositories.lab_ordered_test_repository import (
            lab_visit_services,
            specimen_visit_service_orders,
            unallocated_lab_release_history,
        )

        custody = specimen_visit_service_orders().subquery()
        if (
            self.db.scalar(
                select(custody.c.visit_service_id)
                .where(
                    custody.c.visit_service_id.in_(selected_ids),
                    custody.c.order_id != instance.order_id,
                )
                .limit(1)
            )
            is not None
        ):
            raise LabReportingDomainError(
                409, "Ordered service has specimen custody in another lab order"
            )

        history = unallocated_lab_release_history().subquery()
        if (
            self.db.scalar(
                select(VisitService.id)
                .join(
                    history,
                    history.c.visit_id == VisitService.visit_id,
                )
                .where(
                    VisitService.id.in_(selected_ids),
                    (
                        (history.c.missing_release_dates > 0)
                        | (VisitService.created_at <= history.c.latest_release)
                    ),
                )
                .limit(1)
            )
            is not None
        ):
            raise LabReportingDomainError(
                409, "Ordered service has unconfirmed historical report coverage"
            )

        lab_services = lab_visit_services().subquery()
        codes_by_id = {
            row.visit_service_id: normalize_service_code(row.code or "")
            for row in self.db.execute(
                select(lab_services.c.visit_service_id, lab_services.c.code).where(
                    lab_services.c.visit_service_id.in_(selected_ids),
                )
            )
        }
        allowed_codes = {
            binding.service_code
            for binding in self.repository.list_service_bindings(
                service_codes=list(codes_by_id.values())
            )
            if binding.is_active and binding.template_code == template_code
        }
        if not all(codes_by_id.get(row.id) in allowed_codes for row in rows):
            raise LabReportingDomainError(
                409, "Template does not match the selected laboratory service"
            )
        for row in rows:
            self.db.add(
                LabOrderTest(
                    order_id=instance.order_id,
                    visit_service_id=row.id,
                    report_instance_id=instance.id,
                )
            )
