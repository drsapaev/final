"""Instances mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

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
    ) -> LabReportInstance:
        logger.info(
            "[LAB] create_instance has_appointment_context=%s has_visit_context=%s has_template_version=%s",
            payload.get("appointment_id") is not None,
            payload.get("visit_id") is not None,
            payload.get("template_version_id") is not None,
        )
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

        signer_overrides = payload.get("signer_overrides") or {}
        branding_overrides = payload.get("branding_overrides") or {}
        instance = LabReportInstance(
            order_id=order.id if order else None,
            visit_id=visit_id,
            patient_id=patient.id,
            template_id=template.id,
            template_version_id=version.id,
            status="DRAFT",
            patient_snapshot=self._build_patient_snapshot(patient),
            branding_snapshot=self._build_branding_snapshot(version, branding_overrides),
            signer_snapshot=self._build_signer_snapshot(
                version,
                signer_overrides,
                actor_name=actor_name,
            ),
        )
        self.repository.add_instance(instance)
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
        self, instance_id: int, payload: dict[str, Any], expected_updated_at: str | None = None
    ) -> LabReportInstance:
        logger.info("[LAB] update_instance instance_id=%s", instance_id)
        instance = self.get_instance(instance_id)
        self._assert_instance_editable(instance)
        # WF-06 fix: optimistic locking — проверяем что никто не изменил
        # бланк с момента последнего чтения frontend'ом.
        self._assert_not_concurrently_modified(instance, expected_updated_at)
        if "signer_snapshot" in payload and payload["signer_snapshot"] is not None:
            instance.signer_snapshot = payload["signer_snapshot"]
        if "branding_snapshot" in payload and payload["branding_snapshot"] is not None:
            instance.branding_snapshot = payload["branding_snapshot"]
        self.repository.commit()
        return self.get_instance(instance.id)


    def bulk_upsert_values(
        self, instance_id: int, values_payload: list[dict[str, Any]],
        expected_updated_at: str | None = None,
    ) -> tuple[LabReportInstance, list[LabReportValue]]:
        logger.info(
            "[LAB] bulk_upsert_values instance_id=%s items=%s",
            instance_id,
            len(values_payload),
        )
        instance = self.get_instance(instance_id)
        self._assert_instance_editable(instance)
        # WF-06 fix: optimistic locking — проверяем что никто не изменил
        # бланк с момента последнего чтения frontend'ом.
        self._assert_not_concurrently_modified(instance, expected_updated_at)
        field_map = self._field_map(instance.template_version)
        existing_by_key = {value.field_key: value for value in instance.values}
        current_values = {
            value.field_key: self._extract_effective_value(value)
            for value in instance.values
        }

        updated_values: list[LabReportValue] = []
        for item in values_payload:
            field_key = item["field_key"]
            field_def = field_map.get(field_key)
            if not field_def:
                raise LabReportingDomainError(404, f"Field '{field_key}' not found in template")
            normalized = self._normalize_value_payload(item, field_def)
            current_values[field_key] = normalized["effective_value"]
            context = self._build_rule_context(instance.patient_snapshot, current_values)
            reference = self._resolve_reference(field_def, context)
            flag = self._resolve_flag(
                field_def=field_def,
                effective_value=normalized["effective_value"],
                context=context,
                reference=reference,
            )

            lab_value = existing_by_key.get(field_key)
            if lab_value is None:
                lab_value = LabReportValue(instance_id=instance.id, field_key=field_key)
                instance.values.append(lab_value)
                existing_by_key[field_key] = lab_value

            lab_value.value_text = normalized["value_text"]
            lab_value.value_numeric = normalized["value_numeric"]
            lab_value.comment = normalized["comment"]
            lab_value.resolved_reference_text = reference.get("text")
            lab_value.resolved_flag = flag["flag"]
            lab_value.resolved_flag_source = flag["source"]
            lab_value.resolved_flag_severity = flag["severity_rank"]
            lab_value.resolved_flag_meta = flag["meta"]
            updated_values.append(lab_value)

        if instance.status == "DRAFT" and updated_values:
            instance.status = "IN_PROGRESS"
        self.repository.commit()
        return self.get_instance(instance.id), updated_values


    def mark_ready(self, instance_id: int) -> LabReportInstance:
        logger.info("[LAB] mark_ready instance_id=%s", instance_id)
        instance = self.get_instance(instance_id)
        self._assert_instance_editable(instance)
        instance.status = "READY"
        self.repository.commit()
        return self.get_instance(instance.id)

    # ============================================================
    # === FINALIZE & NOTIFY ===
    # ============================================================


    def revise(self, instance_id: int) -> LabReportInstance:
        logger.info("[LAB] revise instance_id=%s", instance_id)
        source = self.get_instance(instance_id)
        if source.status not in FINAL_INSTANCE_STATUSES:
            raise LabReportingDomainError(409, "Only finalized instances can be revised")

        revision = LabReportInstance(
            order_id=source.order_id,
            visit_id=source.visit_id,
            patient_id=source.patient_id,
            template_id=source.template_id,
            template_version_id=source.template_version_id,
            status="DRAFT",
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
        self.repository.commit()
        return self.get_instance(revision.id)


    def mark_printed(self, instance_id: int) -> LabReportInstance:
        logger.info("[LAB] mark_printed instance_id=%s", instance_id)
        instance = self.get_instance(instance_id)
        if instance.status not in {"FINALIZED", "PRINTED"}:
            raise LabReportingDomainError(409, "Only finalized reports can be printed")
        instance.status = "PRINTED"
        instance.printed_at = datetime.now(UTC)
        self.repository.commit()
        return self.get_instance(instance.id)


    def instance_available_actions(self, instance: LabReportInstance) -> list[str]:
        actions: list[str] = []
        if instance.status not in FINAL_INSTANCE_STATUSES:
            actions.extend(["edit", "save_draft", "mark_ready", "finalize"])
        if instance.status in FINAL_INSTANCE_STATUSES:
            actions.extend(["revise", "print"])
        return actions


    def instance_action_flags(self, instance: LabReportInstance) -> dict[str, bool]:
        actions = set(self.instance_available_actions(instance))
        return {
            "can_edit": "edit" in actions,
            "can_save_draft": "save_draft" in actions,
            "can_mark_ready": "mark_ready" in actions,
            "can_finalize": "finalize" in actions,
            "can_revise": "revise" in actions,
            "can_print": "print" in actions,
        }


    def _assert_instance_editable(self, instance: LabReportInstance) -> None:
        if instance.status in FINAL_INSTANCE_STATUSES:
            raise LabReportingDomainError(409, "Finalized reports are immutable; use revise")


    def _assert_not_concurrently_modified(
        self, instance: LabReportInstance, expected_updated_at: str | None
    ) -> None:
        """WF-06 fix: optimistic locking via updated_at.

        Если frontend передал expected_updated_at (ISO string), проверяем
        что instance.updated_at не изменился с момента последнего чтения.
        Если изменился — другой пользователь сохранил изменения, 409 Conflict.

        Это предотвращает silent data loss когда два лаборанта редактируют
        один бланк одновременно (last-write-wins без этой проверки).
        """
        if not expected_updated_at:
            return  # optimistic locking опционален, backward compatible
        try:
            from datetime import datetime
            # Парсим ISO string (frontend передаёт ISO 8601)
            expected_dt = datetime.fromisoformat(
                expected_updated_at.replace("Z", "+00:00")
            )
            actual_dt = instance.updated_at
            if actual_dt and actual_dt.tzinfo is None:
                actual_dt = actual_dt.replace(tzinfo=UTC)
            if expected_dt and actual_dt and abs((actual_dt - expected_dt).total_seconds()) > 1:
                raise LabReportingDomainError(
                    409,
                    "Бланк был изменён другим пользователем. "
                    "Обновите страницу, чтобы получить актуальные данные.",
                )
        except (ValueError, TypeError):
            # Если не удалось распарсить дату — не блокируем (graceful degradation)
            logger.warning(
                "[LAB] _assert_not_concurrently_modified: failed to parse "
                "expected_updated_at=%s, skipping lock check",
                expected_updated_at,
            )


    def _make_clone_code(self, source_code: str) -> str:
        suffix = 2
        while True:
            candidate = f"{source_code}_copy_{suffix}"
            if not self.repository.get_template_by_code(candidate):
                return candidate
            suffix += 1


