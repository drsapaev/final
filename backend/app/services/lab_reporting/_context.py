"""Context mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.crud.clinic import get_queue_settings
from app.repositories.lab_specimen_repository import SpecimenRepository
from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import LabReportingServiceMixinBase
from app.services.lab_reporting._result_values import age_components


class ContextMixin(LabReportingServiceMixinBase):
    """Context methods for LabReportingService."""

    def _validate_template_selection_for_context(
        self,
        *,
        template: LabReportTemplate,
        patient_id: int,
        visit_id: int | None,
        service_codes: list[str] | None,
        service_items: list[dict[str, Any]] | None,
    ) -> None:
        resolution = self.resolve_template_options(
            patient_id=patient_id,
            visit_id=visit_id,
            service_codes=service_codes,
            service_items=service_items,
        )
        resolved_service_codes = resolution["service_codes"]
        allowed_templates = resolution["allowed_templates"]
        if not resolved_service_codes:
            return
        if not allowed_templates:
            raise LabReportingDomainError(
                409,
                "No lab template mapping configured for the selected service context",
            )
        allowed_template_codes = {item.code for item in allowed_templates}
        if template.code not in allowed_template_codes:
            raise LabReportingDomainError(
                409,
                f"Template '{template.name}' is not allowed for services: {', '.join(resolved_service_codes)}",
            )


    def _resolve_visit_context(
        self,
        *,
        visit_id: int | None,
        appointment_id: int | None,
        create_if_missing: bool,
    ) -> int | None:
        if visit_id:
            if not self.repository.get_visit(visit_id):
                raise LabReportingDomainError(404, "Visit not found")
            return visit_id
        if not appointment_id:
            return None
        try:
            resolved_visit_id = CanonicalVisitService(self.db).resolve_canonical_visit(
                appointment_id,
                create_if_missing=create_if_missing,
            )
        except CanonicalVisitResolutionError as exc:
            if not create_if_missing and exc.status_code == 404:
                logger.info(
                    "[LAB] canonical visit is not available yet for appointment context",
                )
                return None
            raise LabReportingDomainError(exc.status_code, exc.detail) from exc
        logger.info(
            "[LAB] resolved visit context has_appointment_context=%s has_resolved_visit_context=%s",
            appointment_id is not None,
            resolved_visit_id is not None,
        )
        return resolved_visit_id


    def _collect_service_context(
        self,
        *,
        visit_id: int | None,
        service_codes: list[str] | None,
        service_items: list[dict[str, Any]] | None,
    ) -> dict[str, list[str]]:
        items = list(service_items or [])
        if visit_id:
            visit_items = self.repository.list_visit_service_context(visit_id)
            if visit_items:
                items.extend(visit_items)

        raw_codes = list(service_codes or [])
        raw_names: list[str] = []
        for item in items:
            code = item.get("code")
            if code:
                raw_codes.append(str(code))
            name = item.get("name")
            if name:
                raw_names.append(str(name).strip())

        return {
            "service_codes": self._normalize_service_codes(raw_codes),
            "service_names": self._dedupe_text_values(raw_names),
        }


    def _normalize_service_codes(self, raw_codes: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for code in raw_codes:
            normalized_code = normalize_service_code(code)
            if not normalized_code or normalized_code in seen:
                continue
            seen.add(normalized_code)
            normalized.append(normalized_code)
        return normalized


    def _dedupe_text_values(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized:
                continue
            lowered = normalized.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(normalized)
        return deduped


    def _resolve_instance_version(
        self, template_id: int, template_version_id: int | None
    ) -> LabReportTemplateVersion:
        if template_version_id:
            version = self.repository.get_template_version(template_version_id)
            if not version or version.template_id != template_id:
                raise LabReportingDomainError(404, "Template version not found")
            return version
        version = self.repository.get_latest_published_version(
            template_id
        ) or self.repository.get_latest_draft_version(template_id)
        if not version:
            raise LabReportingDomainError(404, "No template version available")
        return version


    def _resolve_or_create_order(
        self,
        *,
        order_id: int | None,
        patient_id: int,
        visit_id: int | None,
    ) -> tuple[LabOrder | None, bool]:
        if order_id:
            order = self.repository.get_order(order_id)
            if not order:
                raise LabReportingDomainError(404, "Lab order not found")
            if order.status in {"canceled", "cancelled"}:
                raise LabReportingDomainError(409, "Lab order is canceled")
            self._assert_order_belongs_to_context(
                order=order,
                patient_id=patient_id,
                visit_id=visit_id,
            )
            return order, False
        if visit_id is not None:
            # Collection may provision the same order before a report exists.
            self.db.execute(
                select(Visit.id).where(Visit.id == visit_id).with_for_update(key_share=True)
            )
            orders = self.repository.find_active_orders_by_visit_and_patient(
                visit_id=visit_id,
                patient_id=patient_id,
            )
            if len(orders) > 1:
                raise LabReportingDomainError(409, "Select a lab order explicitly")
            if orders:
                return orders[0], False
        logger.info(
            "[LAB] creating synthetic lab order has_visit_context=%s",
            visit_id is not None,
        )
        return self.repository.add_order(
            LabOrder(
                patient_id=patient_id,
                visit_id=visit_id,
                status="ordered",
                notes="Auto-created from lab report workflow",
            )
        ), True


    def _assert_appointment_belongs_to_patient(
        self, *, appointment_id: int, patient_id: int
    ) -> None:
        appointment = self.db.get(Appointment, appointment_id)
        if not appointment:
            raise LabReportingDomainError(404, "Appointment not found")
        if appointment.patient_id is None or int(appointment.patient_id) != int(
            patient_id
        ):
            raise LabReportingDomainError(
                409, "Appointment does not belong to selected patient"
            )


    def _assert_visit_belongs_to_patient(
        self, *, visit_id: int, patient_id: int
    ) -> None:
        visit = self.repository.get_visit(visit_id)
        if not visit:
            raise LabReportingDomainError(404, "Visit not found")
        if visit.patient_id is None or int(visit.patient_id) != int(patient_id):
            raise LabReportingDomainError(
                409, "Visit does not belong to selected patient"
            )


    def _assert_order_belongs_to_context(
        self,
        *,
        order: LabOrder,
        patient_id: int,
        visit_id: int | None,
    ) -> None:
        if order.patient_id is not None and int(order.patient_id) != int(patient_id):
            raise LabReportingDomainError(
                409, "Lab order does not belong to selected patient"
            )
        if order.visit_id is not None:
            self._assert_visit_belongs_to_patient(
                visit_id=int(order.visit_id),
                patient_id=int(patient_id),
            )
        if order.visit_id != visit_id:
            raise LabReportingDomainError(
                409, "Lab order does not belong to selected visit"
            )


    def _build_patient_snapshot(self, patient, *, study_date: date | None = None) -> dict[str, Any]:
        if study_date is not None and patient.birth_date is not None and study_date < patient.birth_date:
            raise LabReportingDomainError(400, "Study date cannot precede birth date")
        return {
            "patient_id": patient.id,
            "full_name": patient.short_name() if hasattr(patient, "short_name") else patient.first_name,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "middle_name": patient.middle_name,
            "birth_date": patient.birth_date.isoformat() if patient.birth_date else None,
            "sex": patient.sex,
            "study_date": study_date.isoformat() if study_date else None,
            "age_at_date": study_date.isoformat() if study_date else None,
            "age_date_source": "study_date" if study_date else None,
            **age_components(patient.birth_date, study_date),
            "phone": patient.phone,
            "address": patient.address,
        }

    def _set_report_study_date(self, instance: LabReportInstance, study_date: date | None) -> None:
        snapshot = dict(instance.patient_snapshot or {})
        birth_date = date.fromisoformat(snapshot["birth_date"]) if snapshot.get("birth_date") else None
        if study_date is not None and birth_date is not None and study_date < birth_date:
            raise LabReportingDomainError(400, "Study date cannot precede birth date")
        snapshot["study_date"] = study_date.isoformat() if study_date else None
        instance.patient_snapshot = snapshot

    def _refresh_reference_context(self, instance: LabReportInstance) -> dict[str, Any]:
        snapshot = dict(instance.patient_snapshot or {})
        study_date = date.fromisoformat(snapshot["study_date"]) if snapshot.get("study_date") else None
        birth_date = date.fromisoformat(snapshot["birth_date"]) if snapshot.get("birth_date") else None
        specimens = SpecimenRepository(self.db).list_for_report(instance.id)
        if any(specimen.status == "rejected" for specimen in specimens):
            specimens = []
        materials = {specimen.material_code for specimen in specimens}
        material_code = next(iter(materials)) if len(materials) == 1 else None
        reference_date = study_date
        date_source = "study_date" if study_date else None
        collected_times = [specimen.collected_at for specimen in specimens]
        if study_date is None and collected_times and all(timestamp is not None for timestamp in collected_times):
            timezone = ZoneInfo(get_queue_settings(self.db)["timezone"])
            collected_dates = {
                (timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=UTC)).astimezone(timezone).date()
                for timestamp in collected_times if timestamp is not None
            }
            if len(collected_dates) == 1:
                reference_date = next(iter(collected_dates))
                date_source = "specimen_collection"
        snapshot.update({
            "study_date": study_date.isoformat() if study_date else None,
            "age_at_date": reference_date.isoformat() if reference_date else None,
            "age_date_source": date_source,
            "reference_material_code": material_code,
            **age_components(birth_date, reference_date),
        })
        instance.patient_snapshot = snapshot
        return {"material_code": material_code}


    def _build_branding_snapshot(
        self,
        version: LabReportTemplateVersion,
        branding_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        defaults = self.repository.get_clinic_settings_map("clinic")
        snapshot = {
            "clinic_name": defaults.get("clinic_name") or "Doktor Laboratoriyasi",
            "address": defaults.get("address") or "",
            "phone": defaults.get("phone") or "",
            "logo_url": defaults.get("logo_url") or "",
            "document_title": "",
            "document_subtitle": "",
        }
        snapshot.update(version.branding_overrides or {})
        snapshot.update(branding_overrides or {})
        return snapshot


    def _build_signer_snapshot(
        self,
        version: LabReportTemplateVersion,
        signer_overrides: dict[str, Any] | None = None,
        *,
        actor_name: str | None = None,
    ) -> dict[str, Any]:
        snapshot = {
            "lab_technician_label": "Лаборант",
            "lab_technician_name": "",
            "approver_label": "Подпись",
            "approver_name": "",
        }
        snapshot.update(version.signer_defaults or {})
        normalized_actor_name = (actor_name or "").strip()
        if normalized_actor_name:
            snapshot["lab_technician_name"] = normalized_actor_name
            snapshot["approver_name"] = normalized_actor_name
        snapshot.update(signer_overrides or {})
        return snapshot


