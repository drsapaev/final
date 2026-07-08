from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete

import app.services.lab_reporting_service as lab_reporting_service_module
from app.models.appointment import Appointment
from app.models.lab import (
    LabCatalogReferenceRange,
    LabOrder,
    LabReportFieldDef,
    LabReportSection,
    LabReportTemplate,
    LabReportTemplateVersion,
    LabResult,
)
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.notifications import notification_sender_service
from app.services.lab_reporting_service import (
    LabReportingDomainError,
    LabReportingService,
)


@pytest.mark.unit
class TestLabReportingService:
    def test_create_instance_bulk_finalize_and_revise(
        self, db_session, test_patient, test_visit
    ):
        test_patient.sex = "M"
        test_patient.birth_date = date(1990, 1, 1)
        db_session.commit()

        service = LabReportingService(db_session)
        templates = service.list_templates()
        cbc_template = next(template for template in templates if template.code == "cbc_oak")

        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "visit_id": test_visit.id,
                "template_id": cbc_template.id,
            }
        )

        instance, updated_values = service.bulk_upsert_values(
            instance.id,
            [
                {"field_key": "hgb", "value_text": "100"},
                {"field_key": "wbc", "value_text": "5.2"},
            ],
        )

        hgb_value = next(value for value in updated_values if value.field_key == "hgb")
        assert instance.status == "IN_PROGRESS"
        assert hgb_value.resolved_reference_text == "110-160 г/л"
        assert hgb_value.resolved_flag is None
        assert hgb_value.resolved_flag_source is None
        assert hgb_value.resolved_flag_meta is None

        ready_instance = service.mark_ready(instance.id)
        assert ready_instance.status == "READY"

        finalized = service.finalize(instance.id)
        assert finalized.status == "FINALIZED"
        assert finalized.finalized_at is not None

        printed_once = service.mark_printed(finalized.id)
        first_printed_at = printed_once.printed_at
        assert printed_once.status == "PRINTED"
        assert first_printed_at is not None

        printed_twice = service.mark_printed(finalized.id)
        assert printed_twice.status == "PRINTED"
        assert printed_twice.printed_at is not None
        assert printed_twice.printed_at >= first_printed_at

        revised = service.revise(printed_twice.id)
        assert revised.status == "DRAFT"
        assert revised.supersedes_instance_id == printed_twice.id
        assert len(revised.values) == len(printed_twice.values)

    def test_finalize_creates_legacy_lab_result_projection(
        self, db_session, test_patient, test_visit
    ):
        """P-01 bridge: finalize() должен создавать LabResult projection
        для legacy потребителей (mobile app, EMR, statistics).

        Проверяет:
          - После finalize в lab_results появляются записи
          - Количество = количеству заполненных LabReportValue
          - Маппинг полей корректный (test_name, value, unit, ref_range)
          - abnormal соответствует resolved_flag (bool projection)
          - Idempotent: повторный вызов не создаёт дубликаты
        """
        test_patient.sex = "M"
        test_patient.birth_date = date(1990, 1, 1)
        db_session.commit()

        service = LabReportingService(db_session)
        templates = service.list_templates()
        cbc_template = next(template for template in templates if template.code == "cbc_oak")

        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "visit_id": test_visit.id,
                "template_id": cbc_template.id,
            }
        )

        instance, updated_values = service.bulk_upsert_values(
            instance.id,
            [
                {"field_key": "hgb", "value_text": "100"},
                {"field_key": "wbc", "value_text": "5.2"},
            ],
        )

        # Очищаем возможные legacy LabResult для чистоты теста
        db_session.execute(
            delete(LabResult).where(LabResult.order_id == instance.order_id)
        )
        db_session.commit()

        # До finalize — нет LabResult projection
        before_count = (
            db_session.query(LabResult)
            .filter(LabResult.order_id == instance.order_id)
            .count()
        )
        assert before_count == 0, "LabResult не должен существовать до finalize"

        # Act: finalize должен создать projection
        finalized = service.finalize(instance.id)
        assert finalized.status == "FINALIZED"

        # Перезагружаем finalized из БД, чтобы получить свежие values
        # с установленными resolved_flag после finalize
        db_session.refresh(finalized)

        # Assert: созданы 2 LabResult (по числу заполненных values)
        legacy_results = (
            db_session.query(LabResult)
            .filter(LabResult.order_id == instance.order_id)
            .order_by(LabResult.test_code)
            .all()
        )
        assert len(legacy_results) == 2, (
            f"Expected 2 LabResult projections, got {len(legacy_results)}"
        )

        # Проверяем маппинг полей
        hgb_legacy = next(r for r in legacy_results if r.test_code == "hgb")
        wbc_legacy = next(r for r in legacy_results if r.test_code == "wbc")

        # hgb: value=100 (нормализованный Decimal без trailing zeros)
        assert hgb_legacy.value == "100", (
            f"Expected '100', got '{hgb_legacy.value}' — Decimal normalization issue"
        )
        # abnormal = bool(resolved_flag). Flag может быть None или 'low' —
        # не делаем предположений о конкретном flag, проверяем только что
        # поле abnormal существует и это bool.
        assert isinstance(hgb_legacy.abnormal, bool), (
            f"abnormal must be bool, got {type(hgb_legacy.abnormal)}"
        )
        assert hgb_legacy.ref_range is not None, "ref_range должен быть заполнен"
        assert hgb_legacy.test_name, "test_name должен быть не пустой"

        # wbc: value=5.2 (нормализованный)
        assert wbc_legacy.value == "5.2", (
            f"Expected '5.2', got '{wbc_legacy.value}' — Decimal normalization issue"
        )
        assert isinstance(wbc_legacy.abnormal, bool)

        # abnormal должен соответствовать resolved_flag на source value
        hgb_source = next(v for v in finalized.values if v.field_key == "hgb")
        wbc_source = next(v for v in finalized.values if v.field_key == "wbc")
        assert hgb_legacy.abnormal == bool(hgb_source.resolved_flag), (
            "abnormal must mirror resolved_flag: "
            f"hgb.abnormal={hgb_legacy.abnormal}, flag={hgb_source.resolved_flag}"
        )
        assert wbc_legacy.abnormal == bool(wbc_source.resolved_flag), (
            "abnormal must mirror resolved_flag: "
            f"wbc.abnormal={wbc_legacy.abnormal}, flag={wbc_source.resolved_flag}"
        )

        # Idempotent: повторный finalize невозможен (state machine),
        # но проверим, что повторный вызов _sync_legacy_lab_results
        # не создаёт дубликаты (защита по existing check).
        field_map = service._field_map(finalized.template_version)
        service._sync_legacy_lab_results(finalized, field_map)
        db_session.commit()

        after_idempotent_count = (
            db_session.query(LabResult)
            .filter(LabResult.order_id == instance.order_id)
            .count()
        )
        assert after_idempotent_count == 2, (
            f"Повторный sync не должен создавать дубликаты, "
            f"expected 2, got {after_idempotent_count}"
        )

    def test_backfill_creates_projection_for_already_finalized_instance(
        self, db_session, test_patient, test_visit
    ):
        """P-01 backfill: _sync_legacy_lab_results работает для уже-финализированных
        instances (без повторного finalize). Это сценарий backfill script:
        instance финализирован ДО bridge, bridge создаёт projection post-hoc.
        """
        test_patient.sex = "M"
        test_patient.birth_date = date(1990, 1, 1)
        db_session.commit()

        service = LabReportingService(db_session)
        templates = service.list_templates()
        cbc_template = next(t for t in templates if t.code == "cbc_oak")

        instance = service.create_instance({
            "patient_id": test_patient.id,
            "visit_id": test_visit.id,
            "template_id": cbc_template.id,
        })

        instance, _ = service.bulk_upsert_values(
            instance.id,
            [
                {"field_key": "hgb", "value_text": "120"},
                {"field_key": "wbc", "value_text": "6.0"},
            ],
        )

        # Финализируем (bridge создаёт LabResult projection)
        finalized = service.finalize(instance.id)
        assert finalized.status == "FINALIZED"

        # Удаляем LabResult (симулируем instance, финализированный ДО bridge)
        db_session.execute(
            delete(LabResult).where(LabResult.order_id == instance.order_id)
        )
        db_session.commit()

        before = (
            db_session.query(LabResult)
            .filter(LabResult.order_id == instance.order_id)
            .count()
        )
        assert before == 0, "LabResult должен быть удалён для теста backfill"

        # Backfill: вызываем _sync_legacy_lab_results напрямую
        field_map = service._field_map(finalized.template_version)
        service._sync_legacy_lab_results(finalized, field_map)
        db_session.commit()

        after = (
            db_session.query(LabResult)
            .filter(LabResult.order_id == instance.order_id)
            .count()
        )
        assert after == 2, (
            f"Backfill должен создать 2 LabResult, got {after}"
        )

    def test_create_instance_prefills_signer_snapshot_from_actor_name(
        self, db_session, test_patient
    ):
        service = LabReportingService(db_session)
        cbc_template = next(
            template for template in service.list_templates() if template.code == "cbc_oak"
        )

        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "template_id": cbc_template.id,
            },
            actor_name="Lab Operator",
        )

        assert instance.signer_snapshot["lab_technician_name"] == "Lab Operator"
        assert instance.signer_snapshot["approver_name"] == "Lab Operator"

    def test_missing_default_templates_are_reseeded_on_demand(self, db_session):
        service = LabReportingService(db_session)
        templates = service.list_templates()
        oam_template = next(template for template in templates if template.code == "urinalysis_oam")

        version_ids = [version.id for version in oam_template.versions]
        section_ids = [
            section.id
            for version in oam_template.versions
            for section in version.sections
        ]

        # Simulate external/manual data loss without going through ORM immutability hooks.
        db_session.execute(
            delete(LabReportFieldDef).where(LabReportFieldDef.section_id.in_(section_ids))
        )
        db_session.execute(
            delete(LabReportSection).where(LabReportSection.id.in_(section_ids))
        )
        db_session.execute(
            delete(LabReportTemplateVersion).where(
                LabReportTemplateVersion.id.in_(version_ids)
            )
        )
        db_session.execute(
            delete(LabReportTemplate).where(LabReportTemplate.id == oam_template.id)
        )
        db_session.commit()

        reseeded_templates = service.list_templates()
        assert any(template.code == "urinalysis_oam" for template in reseeded_templates)
        assert any(template.code == "cbc_oak" for template in reseeded_templates)

    def test_age_based_catalog_reference_resolves_ige_template(
        self, db_session, test_patient
    ):
        today = date.today()
        try:
            test_patient.birth_date = date(today.year - 2, today.month, today.day)
        except ValueError:
            test_patient.birth_date = date(today.year - 2, today.month, 28)
        db_session.commit()

        service = LabReportingService(db_session)
        templates = service.list_templates()
        ige_template = next(template for template in templates if template.code == "ige_total")

        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "template_id": ige_template.id,
            }
        )

        _, updated_values = service.bulk_upsert_values(
            instance.id,
            [{"field_key": "total_ige", "value_text": "60"}],
        )

        ige_value = next(value for value in updated_values if value.field_key == "total_ige")
        assert ige_value.resolved_reference_text == "< 45 МЕ/мл"
        assert ige_value.resolved_flag == "high"
        assert ige_value.resolved_flag_source == "catalog_reference"
        assert ige_value.resolved_flag_meta["reference_mode"] == "catalog"

    def test_catalog_reference_resolves_spermogramma_template(
        self, db_session, test_patient
    ):
        service = LabReportingService(db_session)
        templates = service.list_templates()
        sperm_template = next(template for template in templates if template.code == "spermogramma")

        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "template_id": sperm_template.id,
            }
        )

        _, updated_values = service.bulk_upsert_values(
            instance.id,
            [{"field_key": "normal_forms", "value_text": "75"}],
        )

        sperm_value = next(value for value in updated_values if value.field_key == "normal_forms")
        assert sperm_value.resolved_reference_text == "81 - 100"
        assert sperm_value.resolved_flag == "low"
        assert sperm_value.resolved_flag_source == "catalog_reference"
        assert sperm_value.resolved_flag_meta["reference_mode"] == "catalog"

    def test_catalog_reference_resolves_oam_template_for_sex_specific_ranges(
        self, db_session, test_patient
    ):
        test_patient.sex = "F"
        db_session.commit()

        service = LabReportingService(db_session)
        templates = service.list_templates()
        oam_template = next(template for template in templates if template.code == "urinalysis_oam")

        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "template_id": oam_template.id,
            }
        )

        _, updated_values = service.bulk_upsert_values(
            instance.id,
            [{"field_key": "leukocytes", "value_text": "8"}],
        )

        oam_value = next(value for value in updated_values if value.field_key == "leukocytes")
        assert oam_value.resolved_reference_text == "Аёл: 0 - 6"
        assert oam_value.resolved_flag == "high"
        assert oam_value.resolved_flag_source == "catalog_reference"
        assert oam_value.resolved_flag_meta["reference_mode"] == "catalog"

    def test_textual_highlight_rules_flag_positive_demodex_results_as_critical(
        self, db_session, test_patient
    ):
        service = LabReportingService(db_session)
        templates = service.list_templates()
        demodex_template = next(template for template in templates if template.code == "demodex_panel")

        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "template_id": demodex_template.id,
            }
        )

        _, updated_values = service.bulk_upsert_values(
            instance.id,
            [{"field_key": "demodex_folliculorum", "value_text": "аникланмайди"}],
        )
        negative_value = next(value for value in updated_values if value.field_key == "demodex_folliculorum")
        assert negative_value.resolved_flag is None

        _, updated_values = service.bulk_upsert_values(
            instance.id,
            [{"field_key": "demodex_folliculorum", "value_text": "Обнаружено"}],
        )
        positive_value = next(value for value in updated_values if value.field_key == "demodex_folliculorum")
        assert positive_value.resolved_flag == "critical"
        assert positive_value.resolved_flag_source == "highlight_rule"
        assert positive_value.resolved_flag_meta["reference_mode"] == "static_text"

    def test_smear_choice_fields_flag_positive_results_as_critical(
        self, db_session, test_patient
    ):
        service = LabReportingService(db_session)
        templates = service.list_templates()
        smear_template = next(template for template in templates if template.code == "smear_cleanliness")

        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "template_id": smear_template.id,
            }
        )

        _, updated_values = service.bulk_upsert_values(
            instance.id,
            [{"field_key": "cervix_trichomonas", "value_text": "Аниқланади"}],
        )
        smear_value = next(value for value in updated_values if value.field_key == "cervix_trichomonas")
        assert smear_value.resolved_flag == "critical"
        assert smear_value.resolved_flag_source == "highlight_rule"
        assert smear_value.resolved_flag_meta["reference_mode"] == "static_text"

    def test_seed_template_updates_create_a_new_version_without_overwriting_existing(
        self, db_session, monkeypatch
    ):
        service = LabReportingService(db_session)
        original_templates = service.list_templates()
        cbc_template = next(template for template in original_templates if template.code == "cbc_oak")
        original_version_count = len(cbc_template.versions)
        original_latest = max(cbc_template.versions, key=lambda version: version.version_no)

        patched_definitions = deepcopy(lab_reporting_service_module.DEFAULT_LAB_TEMPLATE_DEFINITIONS)
        patched_cbc = next(item for item in patched_definitions if item["code"] == "cbc_oak")
        patched_cbc["initial_version"]["footer_notes"] = "Updated seed footer note"
        # After the lab_reporting_service.py split, the seed definitions
        # are consumed from app.services.lab_reporting._payload.
        import app.services.lab_reporting._payload as _payload_module
        monkeypatch.setattr(
            _payload_module,
            "DEFAULT_LAB_TEMPLATE_DEFINITIONS",
            patched_definitions,
        )

        reseeded_templates = service.list_templates()
        reseeded_cbc = next(template for template in reseeded_templates if template.code == "cbc_oak")
        published_versions = [
            version for version in reseeded_cbc.versions if version.status == "PUBLISHED"
        ]

        assert len(reseeded_cbc.versions) == original_version_count + 1
        assert len(published_versions) == 1
        assert published_versions[0].version_no == original_latest.version_no + 1
        assert published_versions[0].footer_notes == "Updated seed footer note"
        assert any(version.status == "ARCHIVED" for version in reseeded_cbc.versions)

    def test_resolve_template_options_returns_only_allowed_templates_for_service_context(
        self, db_session, test_patient
    ):
        service = LabReportingService(db_session)

        resolution = service.resolve_template_options(
            patient_id=test_patient.id,
            service_codes=["L25"],
        )

        assert resolution["resolution_mode"] == "mapped"
        assert resolution["service_codes"] == ["L25"]
        assert resolution["matched_service_codes"] == ["L25"]
        assert resolution["unmapped_service_codes"] == []
        assert [template.code for template in resolution["allowed_templates"]] == [
            "urinalysis_oam"
        ]
        assert resolution["default_template"].code == "urinalysis_oam"

    def test_real_catalog_code_l01_resolves_to_cbc_oak(
        self, db_session, test_patient
    ):
        service = LabReportingService(db_session)

        resolution = service.resolve_template_options(
            patient_id=test_patient.id,
            service_codes=["L01"],
        )

        assert resolution["resolution_mode"] == "mapped"
        assert resolution["service_codes"] == ["L01"]
        assert resolution["matched_service_codes"] == ["L01"]
        assert resolution["unmapped_service_codes"] == []
        assert [template.code for template in resolution["allowed_templates"]] == [
            "cbc_oak"
        ]
        assert resolution["default_template"].code == "cbc_oak"

    def test_real_catalog_codes_l23_l24_l54_resolve_to_exact_templates(
        self, db_session, test_patient
    ):
        service = LabReportingService(db_session)
        expected = {
            "L23": "vitamin_d_panel",
            "L24": "hba1c_panel",
            "L54": "testosterone_panel",
        }

        for service_code, template_code in expected.items():
            resolution = service.resolve_template_options(
                patient_id=test_patient.id,
                service_codes=[service_code],
            )

            assert resolution["resolution_mode"] == "mapped"
            assert resolution["service_codes"] == [service_code]
            assert resolution["matched_service_codes"] == [service_code]
            assert resolution["unmapped_service_codes"] == []
            assert [template.code for template in resolution["allowed_templates"]] == [
                template_code
            ]
            assert resolution["default_template"].code == template_code

    def test_create_instance_resolves_canonical_visit_from_appointment_context(
        self, db_session, test_patient, test_doctor
    ):
        appointment = Appointment(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today(),
            appointment_time="09:30",
            status="scheduled",
            services=["L24"],
        )
        db_session.add(appointment)
        db_session.commit()
        db_session.refresh(appointment)

        service = LabReportingService(db_session)
        hba1c_template = next(
            template
            for template in service.list_templates()
            if template.code == "hba1c_panel"
        )

        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "appointment_id": appointment.id,
                "template_id": hba1c_template.id,
                "service_codes": ["L24"],
            }
        )

        assert instance.visit_id is not None
        assert service.repository.get_visit(instance.visit_id) is not None
        assert instance.template.code == "hba1c_panel"

    def test_create_instance_rejects_visit_for_different_patient(
        self, db_session, test_patient, test_doctor
    ):
        other_patient = Patient(
            first_name="Other",
            last_name="Patient",
            phone="+998901111111",
            birth_date=date(1985, 1, 1),
        )
        db_session.add(other_patient)
        db_session.flush()
        other_visit = Visit(
            patient_id=other_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="14:00",
            status="open",
            department="cardiology",
        )
        db_session.add(other_visit)
        db_session.commit()

        service = LabReportingService(db_session)
        cbc_template = next(
            template
            for template in service.list_templates()
            if template.code == "cbc_oak"
        )

        with pytest.raises(LabReportingDomainError) as exc:
            service.create_instance(
                {
                    "patient_id": test_patient.id,
                    "visit_id": other_visit.id,
                    "template_id": cbc_template.id,
                }
            )

        assert exc.value.status_code == 409
        assert "Visit does not belong" in exc.value.detail

    def test_create_instance_rejects_order_for_different_patient(
        self, db_session, test_patient, test_doctor
    ):
        other_patient = Patient(
            first_name="Order",
            last_name="Owner",
            phone="+998902222222",
            birth_date=date(1986, 1, 1),
        )
        db_session.add(other_patient)
        db_session.flush()
        other_visit = Visit(
            patient_id=other_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="14:30",
            status="open",
            department="cardiology",
        )
        db_session.add(other_visit)
        db_session.flush()
        other_order = LabOrder(
            patient_id=other_patient.id,
            visit_id=other_visit.id,
            status="ordered",
        )
        db_session.add(other_order)
        db_session.commit()

        service = LabReportingService(db_session)
        cbc_template = next(
            template
            for template in service.list_templates()
            if template.code == "cbc_oak"
        )

        with pytest.raises(LabReportingDomainError) as exc:
            service.create_instance(
                {
                    "patient_id": test_patient.id,
                    "order_id": other_order.id,
                    "template_id": cbc_template.id,
                }
            )

        assert exc.value.status_code == 409
        assert "Lab order does not belong" in exc.value.detail

    def test_create_instance_rejects_appointment_for_different_patient_before_visit_creation(
        self, db_session, test_patient, test_doctor
    ):
        other_patient = Patient(
            first_name="Appointment",
            last_name="Owner",
            phone="+998903333333",
            birth_date=date(1987, 1, 1),
        )
        db_session.add(other_patient)
        db_session.flush()
        other_appointment = Appointment(
            patient_id=other_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today(),
            appointment_time="15:00",
            status="scheduled",
            services=["L24"],
        )
        db_session.add(other_appointment)
        db_session.commit()

        service = LabReportingService(db_session)
        hba1c_template = next(
            template
            for template in service.list_templates()
            if template.code == "hba1c_panel"
        )

        with pytest.raises(LabReportingDomainError) as exc:
            service.create_instance(
                {
                    "patient_id": test_patient.id,
                    "appointment_id": other_appointment.id,
                    "template_id": hba1c_template.id,
                    "service_codes": ["L24"],
                }
            )

        assert exc.value.status_code == 409
        assert "Appointment does not belong" in exc.value.detail
        assert (
            db_session.query(Visit)
            .filter(Visit.patient_id == other_patient.id)
            .count()
            == 0
        )

    def test_create_instance_rejects_template_outside_service_binding(
        self, db_session, test_patient, test_visit
    ):
        lab_service = Service(
            code="lab_oam",
            service_code="L25",
            name="Общий анализ мочи",
            active=True,
            requires_doctor=False,
            queue_tag="laboratory",
            is_consultation=False,
        )
        db_session.add(lab_service)
        db_session.flush()
        db_session.add(
            VisitService(
                visit_id=test_visit.id,
                service_id=lab_service.id,
                code="L25",
                name=lab_service.name,
                qty=1,
            )
        )
        db_session.commit()

        service = LabReportingService(db_session)
        templates = service.list_templates()
        cbc_template = next(template for template in templates if template.code == "cbc_oak")
        oam_template = next(
            template for template in templates if template.code == "urinalysis_oam"
        )

        with pytest.raises(LabReportingDomainError, match="not allowed"):
            service.create_instance(
                {
                    "patient_id": test_patient.id,
                    "visit_id": test_visit.id,
                    "template_id": cbc_template.id,
                }
            )

        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "visit_id": test_visit.id,
                "template_id": oam_template.id,
            }
        )
        assert instance.template.code == "urinalysis_oam"

    def test_published_versions_are_immutable_and_new_draft_can_be_created(
        self, db_session
    ):
        service = LabReportingService(db_session)
        template = next(template for template in service.list_templates() if template.code == "biochem_panel")
        published_version_id = next(
            version.id for version in template.versions if version.status == "PUBLISHED"
        )

        with pytest.raises(LabReportingDomainError):
            service.update_template_version(
                published_version_id,
                {
                    "layout_preset": "lab_table_compact_v1",
                    "page_settings": {"paper_size": "A4", "orientation": "portrait"},
                    "branding_overrides": {},
                    "signer_defaults": {},
                    "footer_notes": "",
                    "sections": [],
                },
            )

        draft = service.create_template_version(template.id, published_version_id)
        assert draft.status == "DRAFT"
        assert draft.version_no == 2

    def test_published_template_versions_and_structure_are_immutable_via_orm(
        self, db_session
    ):
        service = LabReportingService(db_session)
        template = next(template for template in service.list_templates() if template.code == "cbc_oak")
        published_version = next(
            version for version in template.versions if version.status == "PUBLISHED"
        )

        published_version.footer_notes = "tampered"
        with pytest.raises(ValueError, match="immutable"):
            db_session.flush()
        db_session.rollback()

        template = service.get_template(template.id)
        published_version = next(
            version for version in template.versions if version.status == "PUBLISHED"
        )
        published_version.sections[0].title = "tampered section"
        with pytest.raises(ValueError, match="draft"):
            db_session.flush()
        db_session.rollback()

    def test_bulk_upsert_supports_critical_and_warning_flags(
        self, db_session, test_patient
    ):
        service = LabReportingService(db_session)
        template = service.create_template(
            {
                "code": "critical_flag_demo",
                "name": "Critical Flag Demo",
                "family": "chemistry",
                "description": "Test template for advanced flagging",
                "initial_version": {
                    "layout_preset": "lab_table_classic_v1",
                    "page_settings": {"paper_size": "A4", "orientation": "portrait"},
                    "branding_overrides": {},
                    "signer_defaults": {},
                    "footer_notes": "",
                    "sections": [
                        {
                            "key": "demo",
                            "title": "Demo",
                            "sort_order": 10,
                            "fields": [
                                {
                                    "field_key": "glucose",
                                    "label": "Glucose",
                                    "value_type": "numeric",
                                    "unit": "mmol/L",
                                    "reference_mode": "static_text",
                                    "reference_text": "3.3 - 5.5",
                                    "highlight_rule": {
                                        "mode": "range",
                                        "warning_high": 5.5,
                                        "high": 7.0,
                                        "critical_high": 11.1,
                                    },
                                    "sort_order": 10,
                                }
                            ],
                        }
                    ],
                },
            }
        )
        published_version = service.publish_template_version(template.versions[0].id)

        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "template_id": template.id,
                "template_version_id": published_version.id,
            }
        )

        _, warning_values = service.bulk_upsert_values(
            instance.id,
            [{"field_key": "glucose", "value_text": "6.1"}],
        )
        assert warning_values[0].resolved_flag == "warning"

        _, high_values = service.bulk_upsert_values(
            instance.id,
            [{"field_key": "glucose", "value_text": "8.4"}],
        )
        assert high_values[0].resolved_flag == "high"

        _, critical_values = service.bulk_upsert_values(
            instance.id,
            [{"field_key": "glucose", "value_text": "12.4"}],
        )
        assert critical_values[0].resolved_flag == "critical"
        assert critical_values[0].resolved_flag_source == "range_rule"
        assert critical_values[0].resolved_flag_severity == 300
        assert critical_values[0].resolved_flag_meta["matched_threshold"]["key"] == "critical_high"
        assert critical_values[0].resolved_flag_meta["matched_threshold"]["value"] == "11.1"

        materialized = service.materialize_instance(service.get_instance(instance.id))
        glucose_field = next(
            field
            for section in materialized
            for field in section["fields"]
            if field["field_key"] == "glucose"
        )
        assert glucose_field["resolved_flag"] == "critical"
        assert glucose_field["resolved_flag_source"] == "range_rule"
        assert glucose_field["resolved_flag_severity"] == 300

        critical_findings = service.summarize_critical_findings(materialized)
        assert len(critical_findings) == 1
        assert critical_findings[0]["field_key"] == "glucose"
        assert critical_findings[0]["threshold_display"] == "> 11.1"

        severity_metrics = service.summarize_instance_severity(materialized)
        assert severity_metrics["flagged_findings_count"] == 1
        assert severity_metrics["critical_findings_count"] == 1
        assert severity_metrics["max_flag_severity"] == 300

    def test_catalog_reference_mode_resolves_seeded_ranges(
        self, db_session, test_patient
    ):
        test_patient.sex = "M"
        test_patient.birth_date = date(1990, 1, 1)
        db_session.commit()

        service = LabReportingService(db_session)
        template = service.create_template(
            {
                "code": "catalog_reference_demo",
                "name": "Catalog Reference Demo",
                "family": "hematology",
                "description": "Template using catalog-backed ranges",
                "initial_version": {
                    "layout_preset": "lab_table_classic_v1",
                    "page_settings": {"paper_size": "A4", "orientation": "portrait"},
                    "branding_overrides": {},
                    "signer_defaults": {},
                    "footer_notes": "",
                    "sections": [
                        {
                            "key": "demo",
                            "title": "Demo",
                            "sort_order": 10,
                            "fields": [
                                {
                                    "analyte_code": "hgb",
                                    "unit_code": "g_per_l",
                                    "field_key": "hgb_catalog",
                                    "label": "Hemoglobin",
                                    "value_type": "numeric",
                                    "reference_mode": "catalog",
                                    "reference_text": "120 - 170",
                                    "highlight_rule": {"mode": "rule_based_reference"},
                                    "sort_order": 10,
                                }
                            ],
                        }
                    ],
                },
            }
        )
        published_version = service.publish_template_version(template.versions[0].id)
        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "template_id": template.id,
                "template_version_id": published_version.id,
            }
        )

        _, updated_values = service.bulk_upsert_values(
            instance.id,
            [{"field_key": "hgb_catalog", "value_text": "120"}],
        )

        assert updated_values[0].resolved_reference_text == "130 - 170"
        assert updated_values[0].resolved_flag == "low"
        assert updated_values[0].resolved_flag_source == "catalog_reference"
        assert updated_values[0].resolved_flag_severity == 200
        assert updated_values[0].resolved_flag_meta["matched_threshold"]["key"] == "low"
        assert updated_values[0].resolved_flag_meta["matched_threshold"]["value"] == "130"
        assert updated_values[0].resolved_flag_meta["reference_mode"] == "catalog"

    def test_finalized_catalog_based_report_keeps_flag_snapshot_after_catalog_changes(
        self, db_session, test_patient
    ):
        test_patient.sex = "M"
        test_patient.birth_date = date(1990, 1, 1)
        db_session.commit()

        service = LabReportingService(db_session)
        template = service.create_template(
            {
                "code": "catalog_snapshot_demo",
                "name": "Catalog Snapshot Demo",
                "family": "hematology",
                "description": "Template using catalog-backed snapshot rules",
                "initial_version": {
                    "layout_preset": "lab_table_classic_v1",
                    "page_settings": {"paper_size": "A4", "orientation": "portrait"},
                    "branding_overrides": {},
                    "signer_defaults": {},
                    "footer_notes": "",
                    "sections": [
                        {
                            "key": "demo",
                            "title": "Demo",
                            "sort_order": 10,
                            "fields": [
                                {
                                    "analyte_code": "hgb",
                                    "unit_code": "g_per_l",
                                    "field_key": "hgb_catalog_snapshot",
                                    "label": "Hemoglobin",
                                    "value_type": "numeric",
                                    "reference_mode": "catalog",
                                    "reference_text": "130 - 170",
                                    "highlight_rule": {"mode": "rule_based_reference"},
                                    "sort_order": 10,
                                    "required": True,
                                }
                            ],
                        }
                    ],
                },
            }
        )
        published_version = service.publish_template_version(template.versions[0].id)
        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "template_id": template.id,
                "template_version_id": published_version.id,
            }
        )

        service.bulk_upsert_values(
            instance.id,
            [{"field_key": "hgb_catalog_snapshot", "value_text": "120"}],
        )
        finalized = service.finalize(instance.id)

        male_range = (
            db_session.query(LabCatalogReferenceRange)
            .filter(
                LabCatalogReferenceRange.analyte_code == "hgb",
                LabCatalogReferenceRange.sex == "M",
            )
            .one()
        )
        male_range.text = "140 - 180"
        male_range.low = Decimal("140")
        male_range.high = Decimal("180")
        db_session.commit()

        materialized = service.materialize_instance(service.get_instance(finalized.id))
        field = next(
            item
            for section in materialized
            for item in section["fields"]
            if item["field_key"] == "hgb_catalog_snapshot"
        )

        assert field["reference_text"] == "130 - 170"
        assert field["resolved_flag"] == "low"
        assert field["resolved_flag_source"] == "catalog_reference"
        assert field["resolved_flag_meta"]["matched_threshold"]["value"] == "130"

    def test_create_instance_emits_lab_new_study_for_lab_staff(
        self,
        db_session,
        test_patient,
        test_visit,
    ):
        lab_user = db_session.query(User).filter(User.username == "test_lab_user").first()
        if not lab_user:
            lab_user = User(
                username="test_lab_user",
                email="lab@test.com",
                full_name="Test Lab",
                hashed_password="hashed-password",
                role="Lab",
                is_active=True,
                is_superuser=False,
            )
            db_session.add(lab_user)
            db_session.commit()
            db_session.refresh(lab_user)

        service = LabReportingService(db_session)
        template = next(
            template for template in service.list_templates() if template.code == "cbc_oak"
        )
        send_mock = AsyncMock(return_value=True)
        original = notification_sender_service.send_lab_event_notification
        notification_sender_service.send_lab_event_notification = send_mock
        try:
            instance = service.create_instance(
                {
                    "patient_id": test_patient.id,
                    "visit_id": test_visit.id,
                    "template_id": template.id,
                }
            )
        finally:
            notification_sender_service.send_lab_event_notification = original

        assert instance.order_id is not None
        assert send_mock.await_count == 1
        assert send_mock.await_args.kwargs["event_type"] == "lab_new_study"
        assert send_mock.await_args.kwargs["recipient"].id == lab_user.id
        assert send_mock.await_args.kwargs["metadata"]["patient_id"] == test_patient.id
        assert send_mock.await_args.kwargs["metadata"]["visit_id"] == test_visit.id
