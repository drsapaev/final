"""Instances mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

import hmac
import json
from datetime import date, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.models.lab_release import LabDraftMutationReceipt
from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import LabReportingServiceMixinBase


class InstancesMixin(LabReportingServiceMixinBase):
    """Instances methods for LabReportingService."""

    def list_instances(
        self,
        *,
        patient_id: int | None,
        visit_ids: list[int] | None = None,
        status: str | None,
        limit: int,
        offset: int,
        hide_managed_drafts: bool = False,
    ) -> list[LabReportInstance]:
        logger.info(
            "[LAB] list_instances has_patient_filter=%s visit_filter_count=%s status=%s limit=%s offset=%s",
            patient_id is not None,
            len(visit_ids or []),
            status,
            limit,
            offset,
        )
        return self.repository.list_instances(
            patient_id=patient_id,
            visit_ids=visit_ids,
            status=status,
            limit=limit,
            offset=offset,
            hide_managed_drafts=hide_managed_drafts,
        )


    def get_instance(self, instance_id: int) -> LabReportInstance:
        logger.info("[LAB] get_instance instance_id=%s", instance_id)
        instance = self.repository.get_instance(instance_id)
        if not instance:
            raise LabReportingDomainError(404, "Lab report instance not found")
        return instance

    # ============================================================
    # === INSTANCE MANAGEMENT ===
    # ============================================================


    def create_instance(
        self,
        payload: dict[str, Any],
        *,
        actor_name: str | None = None,
        actor_user_id: int | None = None,
    ) -> LabReportInstance:
        logger.info(
            "[LAB] create_instance has_appointment_context=%s has_visit_context=%s has_template_version=%s",
            payload.get("appointment_id") is not None,
            payload.get("visit_id") is not None,
            payload.get("template_version_id") is not None,
        )
        if settings.LAB_MANAGED_RELEASE_ENABLED:
            self._workflow_actor(actor_user_id)
        patient = self.repository.get_patient(payload["patient_id"])
        if not patient:
            raise LabReportingDomainError(404, "Patient not found")

        appointment_id = payload.get("appointment_id")
        if appointment_id:
            self._assert_appointment_belongs_to_patient(
                appointment_id=int(appointment_id),
                patient_id=int(patient.id),
            )

        visit_id = self._resolve_visit_context(
            visit_id=payload.get("visit_id"),
            appointment_id=appointment_id,
            create_if_missing=True,
        )
        if visit_id is None and payload.get("order_id"):
            explicit_order = self.repository.get_order(payload["order_id"])
            if explicit_order is not None:
                self._assert_order_belongs_to_context(
                    order=explicit_order, patient_id=patient.id, visit_id=explicit_order.visit_id,
                )
                visit_id = explicit_order.visit_id
        if visit_id:
            self._assert_visit_belongs_to_patient(
                visit_id=int(visit_id),
                patient_id=int(patient.id),
            )

        template = self.get_template(payload["template_id"])
        version = self._resolve_instance_version(
            template.id, payload.get("template_version_id")
        )
        self._validate_template_selection_for_context(
            template=template,
            patient_id=patient.id,
            visit_id=visit_id,
            service_codes=payload.get("service_codes"),
            service_items=payload.get("service_items"),
        )
        order, created_new_order = self._resolve_or_create_order(
            order_id=payload.get("order_id"),
            patient_id=patient.id,
            visit_id=visit_id,
        )
        if order is not None:
            due_at = payload.get("order_due_at")
            priority = payload.get("order_priority")
            if due_at is not None:
                current_due = order.due_at
                if current_due is not None and current_due.tzinfo is None:
                    current_due = current_due.replace(tzinfo=UTC)
                if current_due is not None and current_due != due_at:
                    raise LabReportingDomainError(409, "Lab order already has a different due date")
                order.due_at = due_at.astimezone(UTC)
            if priority is not None:
                if order.priority is not None and order.priority != priority:
                    raise LabReportingDomainError(409, "Lab order already has a different priority")
                order.priority = priority

        signer_overrides = payload.get("signer_overrides") or {}
        branding_overrides = payload.get("branding_overrides") or {}
        instance = LabReportInstance(
            order_id=order.id if order else None,
            visit_id=visit_id,
            patient_id=patient.id,
            template_id=template.id,
            template_version_id=version.id,
            status="DRAFT",
            managed_release=settings.LAB_MANAGED_RELEASE_ENABLED,
            patient_snapshot=self._build_patient_snapshot(patient, study_date=payload.get("study_date")),
            branding_snapshot=self._build_branding_snapshot(version, branding_overrides),
            signer_snapshot=self._build_signer_snapshot(
                version,
                signer_overrides,
                actor_name=actor_name,
            ),
        )
        self.repository.add_instance(instance)
        self._claim_ordered_services(instance, payload.get("visit_service_ids") or [], template.code)
        self.repository.commit()
        if created_new_order and order is not None:
            self._emit_lab_new_study_notification(
                order=order,
                patient_id=patient.id,
                visit_id=visit_id,
            )
        logger.info("[LAB] create_instance created instance_id=%s", instance.id)
        return self.get_instance(instance.id)


    def update_instance(
        self, instance_id: int, payload: dict[str, Any], expected_updated_at: str | None = None,
        *, actor_user_id: int | None = None, commit: bool = True,
        draft_request_id: UUID | None = None,
    ) -> LabReportInstance:
        logger.info("[LAB] update_instance instance_id=%s", instance_id)
        instance = self._get_locked_instance(instance_id)
        self._assert_instance_mutable_draft(instance)
        actor = (
            self._workflow_actor(actor_user_id)
            if instance.managed_release or actor_user_id is not None or draft_request_id is not None
            else None
        )
        receipt, replay = self._prepare_draft_write(
            instance, actor, "metadata", draft_request_id, expected_updated_at, payload,
        )
        if replay:
            if commit:
                self.repository.commit()
            return instance
        changed = False
        edited_metadata = False
        if "signer_snapshot" in payload and payload["signer_snapshot"] is not None:
            edited_metadata = instance.signer_snapshot != payload["signer_snapshot"]
            instance.signer_snapshot = payload["signer_snapshot"]
            changed = True
        if "branding_snapshot" in payload and payload["branding_snapshot"] is not None:
            edited_metadata |= instance.branding_snapshot != payload["branding_snapshot"]
            instance.branding_snapshot = payload["branding_snapshot"]
            changed = True
        if "study_date" in payload:
            previous_study_date = (instance.patient_snapshot or {}).get("study_date")
            self._set_report_study_date(instance, payload["study_date"])
            self._refresh_result_evaluation(instance)
            edited_metadata |= previous_study_date != instance.patient_snapshot.get(
                "study_date"
            )
            changed = True
        # Accepted draft writes still advance the optimistic version. Only
        # actual metadata edits belong in the audit trail.
        if changed:
            self._advance_instance_version(instance)
        if edited_metadata and actor is not None:
            self._record_report_draft_edit(instance, actor)
        if receipt is not None:
            receipt.applied_version = instance.updated_at
            self.repository.add_draft_mutation_receipt(receipt)
        if not commit:
            self._flush_draft_response(instance, refresh=receipt is not None)
            return instance
        self.repository.commit()
        return self.get_instance(instance.id)


    def bulk_upsert_values(
        self, instance_id: int, values_payload: list[dict[str, Any]],
        expected_updated_at: str | None = None,
        *, actor_user_id: int | None = None, commit: bool = True,
        source_specimen_id: int | None = None,
        import_origins: dict[str, dict[str, Any]] | None = None,
        draft_request_id: UUID | None = None,
    ) -> tuple[LabReportInstance, list[LabReportValue]]:
        logger.info(
            "[LAB] bulk_upsert_values instance_id=%s items=%s",
            instance_id,
            len(values_payload),
        )
        instance = self._get_locked_instance(instance_id)
        self._assert_instance_mutable_draft(instance)
        actor = (
            self._workflow_actor(actor_user_id)
            if instance.managed_release or actor_user_id is not None or draft_request_id is not None
            else None
        )
        receipt, replay = self._prepare_draft_write(
            instance, actor, "values", draft_request_id, expected_updated_at,
            {"values": values_payload, "source_specimen_id": source_specimen_id},
        )
        existing_by_key = {value.field_key: value for value in instance.values}
        if replay:
            updated = [existing_by_key[item["field_key"]] for item in values_payload]
            if commit:
                self.repository.commit()
            return instance, updated

        field_map = self._field_map(instance.template_version)
        normalized_by_key = {}
        for item in values_payload:
            field_key = item["field_key"]
            field_def = field_map.get(field_key)
            if not field_def:
                raise LabReportingDomainError(404, f"Field '{field_key}' not found in template")
            if field_key in normalized_by_key:
                raise LabReportingDomainError(400, f"Duplicate value for {field_key}")
            normalized_by_key[field_key] = self._normalize_value_payload(item, field_def)

        specimen_id = source_specimen_id
        if source_specimen_id is not None or (instance.managed_release and normalized_by_key):
            eligible_ids = self._accepted_result_specimen_ids(instance)
            if source_specimen_id is not None and source_specimen_id not in eligible_ids:
                raise LabReportingDomainError(409, "Result specimen is not an accepted report specimen")
            if source_specimen_id is None and len(eligible_ids) == 1:
                specimen_id = next(iter(eligible_ids))

        updated_values: list[LabReportValue] = []
        entered_result = False
        edited_draft = False
        for field_key, normalized in normalized_by_key.items():
            lab_value = existing_by_key.get(field_key)
            if lab_value is None:
                lab_value = LabReportValue(instance_id=instance.id, field_key=field_key)
                instance.values.append(lab_value)
                existing_by_key[field_key] = lab_value

            result = normalized["result_payload"]
            same_measurement = self._same_measurement(
                lab_value, normalized, field_map[field_key],
            )
            previous = lab_value.result_payload or {}
            old_specimen_id = previous.get("source_specimen_id")
            if result and result["kind"] != "absent":
                # Saving a comment or resending the same result cannot silently
                # move a measurement to a recollected specimen.
                result_specimen_id = specimen_id
                if source_specimen_id is None and same_measurement:
                    result_specimen_id = old_specimen_id
                if result_specimen_id is not None:
                    result = {**result, "source_specimen_id": result_specimen_id}
            if result:
                if import_origins is not None:
                    result["import_origin"] = import_origins[field_key]
                elif (
                    same_measurement
                    and result.get("method_code") == previous.get("method_code")
                    and "import_origin" in previous
                ):
                    result["import_origin"] = previous["import_origin"]
            # An explicit import anchored to a different accepted specimen is
            # a new measurement even when its result equals the old one.
            imported_measurement = (
                source_specimen_id is not None
                and result is not None
                and result.get("source_specimen_id") == source_specimen_id
                and source_specimen_id != old_specimen_id
            )
            if result and (not same_measurement or imported_measurement):
                entered_result = True
            edited_draft |= (
                lab_value.value_text != normalized["value_text"]
                or lab_value.value_numeric != normalized["value_numeric"]
                or lab_value.comment != normalized["comment"]
                or lab_value.result_payload != result
            )
            lab_value.value_text = normalized["value_text"]
            lab_value.value_numeric = normalized["value_numeric"]
            lab_value.comment = normalized["comment"]
            lab_value.result_payload = result
            updated_values.append(lab_value)

        self._refresh_result_evaluation(instance)
        if instance.status == "DRAFT" and updated_values:
            instance.status = "IN_PROGRESS"
        self._advance_instance_version(instance)
        if actor is not None:
            if entered_result:
                self._append_workflow_event(instance, kind="entered", actor=actor)
            elif edited_draft:
                self._record_report_draft_edit(instance, actor)
        if receipt is not None:
            receipt.applied_version = instance.updated_at
            self.repository.add_draft_mutation_receipt(receipt)
        if not commit:
            self._flush_draft_response(instance, refresh=receipt is not None)
            return instance, updated_values
        self.repository.commit()
        return self.get_instance(instance.id), updated_values

    def _flush_draft_response(self, instance: LabReportInstance, *, refresh: bool) -> None:
        self.repository.flush()
        if refresh:
            # Reload this identity-map instance under the existing report lock.
            # The DTO must use database values, including stored decimal scale.
            self.repository.get_instance(instance.id, populate_existing=True)

    def _prepare_draft_write(
        self,
        instance: LabReportInstance,
        actor: User | None,
        operation: Literal["metadata", "values"],
        request_id: UUID | None,
        expected_updated_at: str | None,
        payload: dict[str, Any],
    ) -> tuple[LabDraftMutationReceipt | None, bool]:
        """Resolve a retry while holding the lock that protects the draft version."""
        if instance.managed_release or request_id is not None:
            self._workflow_expected_version(expected_updated_at)
        if request_id is None:
            self._assert_not_concurrently_modified(instance, expected_updated_at)
            return None, False
        if actor is None:
            raise LabReportingDomainError(403, "Laboratory workflow access denied")

        # Bind even the original version spelling and bulk item order. Store a
        # keyed digest so low-entropy clinical inputs cannot be guessed from it.
        encoded = json.dumps(
            [instance.id, actor.id, operation, str(request_id), expected_updated_at, payload],
            sort_keys=True, separators=(",", ":"), default=date.isoformat,
        ).encode()
        digest = hmac.new(
            settings.SECRET_KEY.encode(), b"lab-draft-receipt-v1\x00" + encoded, "sha256",
        ).hexdigest()
        previous = self.repository.get_draft_mutation_receipt(
            instance.id, actor.id, operation, request_id,
        )
        if previous is not None:
            if not hmac.compare_digest(digest, previous.request_digest):
                raise LabReportingDomainError(409, "Draft request ID already bound to a different save")
            # Never acknowledge an old operation with another writer's version.
            self._assert_not_concurrently_modified(instance, previous.applied_version.isoformat())
            return None, True

        self._assert_not_concurrently_modified(instance, expected_updated_at)
        return LabDraftMutationReceipt(
            instance_id=instance.id,
            actor_user_id=actor.id,
            operation=operation,
            request_id=request_id,
            request_digest=digest,
            applied_version=instance.updated_at,
        ), False

    def _same_measurement(
        self, value: LabReportValue, normalized: dict[str, Any], field_def: LabReportFieldDef,
    ) -> bool:
        value_text = value.value_text
        value_numeric = value.value_numeric
        before = value.result_payload or None
        if before is None and (value_text is not None or value_numeric is not None):
            # Older copied corrections may have a measured value without
            # structured provenance. A matching resave still proves no source.
            try:
                legacy = self._normalize_value_payload(
                    {"value_text": value_text, "value_numeric": value_numeric}, field_def,
                )
            except LabReportingDomainError:
                return False
            before = legacy["result_payload"]
            value_text = legacy["value_text"]
            value_numeric = legacy["value_numeric"]
        after = normalized["result_payload"]
        if after is None:
            return before is None
        kind = after["kind"]
        if before is None or before.get("kind") != kind:
            return False
        if kind == "text":
            return value_text == normalized["value_text"]
        if kind == "coded_qualitative":
            return before.get("qualitative_code") == after.get("qualitative_code")
        if kind == "absent":
            return before.get("absence_reason") == after.get("absence_reason")
        return (
            value_numeric == normalized["value_numeric"]
            and before.get("comparator") == after.get("comparator")
        )


    def mark_ready(self, instance_id: int) -> LabReportInstance:
        logger.info("[LAB] mark_ready instance_id=%s", instance_id)
        instance = self._get_locked_instance(instance_id)
        self._assert_instance_editable(instance)
        if instance.managed_release:
            raise LabReportingDomainError(409, "Use the managed review workflow")
        instance.status = "READY"
        self._advance_instance_version(instance)
        self.repository.commit()
        return self.get_instance(instance.id)

    # ============================================================
    # === FINALIZE & NOTIFY ===
    # ============================================================


    def revise(
        self, instance_id: int, *, actor_user_id: int | None = None,
        expected_updated_at: str | None = None, reason: str | None = None,
    ) -> LabReportInstance:
        logger.info("[LAB] revise instance_id=%s", instance_id)
        source = self._get_locked_instance(instance_id)
        if source.status not in FINAL_INSTANCE_STATUSES:
            raise LabReportingDomainError(409, "Only finalized instances can be revised")
        managed = source.managed_release or settings.LAB_MANAGED_RELEASE_ENABLED
        actor = self._workflow_actor(actor_user_id) if managed or actor_user_id is not None else None
        expected_version = None
        if managed:
            reason = self._workflow_reason(reason)
            expected_version = self._workflow_expected_version(expected_updated_at)
            existing_id = self.db.scalar(select(LabReportInstance.id).where(
                LabReportInstance.supersedes_instance_id == source.id,
            ).order_by(LabReportInstance.id).limit(1))
            if existing_id is not None:
                event = self._latest_workflow_event(existing_id, "revision_created")
                if (
                    event
                    and event.actor_user_id == actor.id
                    and event.reason == reason
                    and event.expected_version
                    and self._normalized_version(event.expected_version) == expected_version
                ):
                    return self.get_instance(existing_id)
                raise LabReportingDomainError(409, "A correction already exists for this report version")
        elif reason is not None:
            reason = self._workflow_reason(reason)
        self._assert_not_concurrently_modified(source, expected_updated_at)

        revision = LabReportInstance(
            order_id=source.order_id,
            visit_id=source.visit_id,
            patient_id=source.patient_id,
            template_id=source.template_id,
            template_version_id=source.template_version_id,
            status="DRAFT",
            managed_release=managed,
            patient_snapshot=deepcopy(source.patient_snapshot),
            branding_snapshot=deepcopy(source.branding_snapshot),
            signer_snapshot=deepcopy(source.signer_snapshot),
            supersedes_instance_id=source.id,
        )
        self.repository.add_instance(revision)
        for value in source.values:
            revision.values.append(
                LabReportValue(
                    field_key=value.field_key,
                    value_text=value.value_text,
                    value_numeric=value.value_numeric,
                    result_payload=deepcopy(value.result_payload),
                    evaluation_snapshot=deepcopy(value.evaluation_snapshot),
                    resolved_reference_text=value.resolved_reference_text,
                    resolved_flag=value.resolved_flag,
                    resolved_flag_source=value.resolved_flag_source,
                    resolved_flag_severity=value.resolved_flag_severity,
                    resolved_flag_meta=deepcopy(value.resolved_flag_meta)
                    if value.resolved_flag_meta
                    else None,
                    comment=value.comment,
                )
            )
        if actor is not None:
            self._append_workflow_event(
                revision, kind="revision_created", actor=actor,
                expected_version=expected_version, reason=reason,
            )
        self.repository.commit()
        return self.get_instance(revision.id)


    def mark_printed(self, instance_id: int) -> LabReportInstance:
        logger.info("[LAB] mark_printed instance_id=%s", instance_id)
        instance = self._get_locked_instance(instance_id)
        if instance.status not in {"FINALIZED", "PRINTED"}:
            raise LabReportingDomainError(409, "Only finalized reports can be printed")
        instance.status = "PRINTED"
        instance.printed_at = datetime.now(UTC)
        self._advance_instance_version(instance)
        self.repository.commit()
        return self.get_instance(instance.id)


    def instance_available_actions(
        self, instance: LabReportInstance, actor_user_id: int | None = None,
    ) -> list[str]:
        if instance.managed_release:
            return self.managed_workflow_actions(instance, actor_user_id)
        actions: list[str] = []
        if instance.status not in FINAL_INSTANCE_STATUSES:
            # PR8: preview — серверный A4-рендер сохранённых значений без
            # утверждения (endpoint /report-instances/{id}/preview, Admin/Lab).
            actions.extend(["edit", "save_draft", "mark_ready", "finalize", "preview"])
        if instance.status in FINAL_INSTANCE_STATUSES:
            actions.extend(["revise", "print"])
        return actions


    def instance_action_flags(
        self, instance: LabReportInstance, actor_user_id: int | None = None,
        *, available_actions: list[str] | None = None,
    ) -> dict[str, bool]:
        actions = set(available_actions) if available_actions is not None else set(
            self.instance_available_actions(instance, actor_user_id)
        )
        return {
            "can_edit": "edit" in actions,
            "can_save_draft": "save_draft" in actions,
            "can_mark_ready": "mark_ready" in actions,
            "can_finalize": "finalize" in actions,
            "can_revise": "revise" in actions,
            "can_print": "print" in actions,
            # PR8: preview доступен только неутверждённым бланкам; после
            # finalize используется print (+ /pdf без watermark).
            "can_preview": "preview" in actions,
        }


    def _assert_instance_editable(self, instance: LabReportInstance) -> None:
        if instance.status in FINAL_INSTANCE_STATUSES:
            raise LabReportingDomainError(409, "Finalized reports are immutable; use revise")


    def _get_locked_instance(self, instance_id: int) -> LabReportInstance:
        instance = self.repository.get_instance_for_update(instance_id)
        if not instance:
            raise LabReportingDomainError(404, "Lab report instance not found")
        return instance


    @staticmethod
    def _normalized_version(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


    def _advance_instance_version(self, instance: LabReportInstance) -> None:
        """Advance the opaque server token even on same-clock-tick writes."""
        current = self._normalized_version(instance.updated_at)
        instance.updated_at = max(
            datetime.now(UTC),
            current + timedelta(microseconds=1),
        )


    def _assert_not_concurrently_modified(
        self, instance: LabReportInstance, expected_updated_at: str | None
    ) -> None:
        """Compare an optional opaque server version exactly under row lock."""
        if expected_updated_at is None:
            return
        try:
            if len(expected_updated_at) < 19:
                raise ValueError("Expected a full timestamp")
            expected_dt = datetime.fromisoformat(
                expected_updated_at.replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            raise LabReportingDomainError(
                400,
                "Некорректная версия бланка. "
                "Обновите страницу, чтобы получить актуальные данные.",
            ) from None

        expected_dt = self._normalized_version(expected_dt)
        actual_dt = self._normalized_version(instance.updated_at)
        if actual_dt != expected_dt:
            raise LabReportingDomainError(
                409,
                "Бланк был изменён другим пользователем. "
                "Обновите страницу, чтобы получить актуальные данные.",
            )


    def _make_clone_code(self, source_code: str) -> str:
        suffix = 2
        while True:
            candidate = f"{source_code}_copy_{suffix}"
            if not self.repository.get_template_by_code(candidate):
                return candidate
            suffix += 1


