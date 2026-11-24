"""Advisory autoverification over a synthetic managed laboratory workflow."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.crud import audit as audit_crud
from app.models.lab_specimen import LabSpecimen, LabSpecimenAssignment
from app.models.patient import Patient
from app.models.role_permission import Permission, Role, user_roles_table
from app.models.user import User
from app.schemas.lab_release import LabReportQCIn
from app.services.lab_reporting._autoverification import (
    ShadowEvidence,
    ShadowFieldRule,
    ShadowRuleSet,
    evaluate_autoverification_shadow,
)
from app.services.lab_reporting_service import LabReportingService

pytestmark = pytest.mark.unit
FIELD_KEY = "synthetic_result"
HIDDEN_FIELD_KEY = "synthetic_hidden_result"


@pytest.fixture
def shadow_service(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LAB_MANAGED_RELEASE_ENABLED", True)
    monkeypatch.setattr(settings, "LAB_AUTOVERIFICATION_SHADOW_ENABLED", True)
    return LabReportingService(db_session)


@pytest.fixture
def make_report(shadow_service, db_session):
    service = shadow_service
    patient = Patient(first_name="SYNTHETIC", last_name="SHADOW")
    actor = User(
        username="SYNTHETIC-shadow-staff",
        full_name="SYNTHETIC SHADOW STAFF",
        hashed_password="unusable",
        role="Lab",
        is_active=True,
    )
    qc_role = Role(
        name="synthetic-shadow-qc",
        display_name="SYNTHETIC SHADOW QC",
        permissions=[Permission(name="lab:qc", codename="lab:qc")],
    )
    db_session.add_all([patient, actor, qc_role])
    db_session.flush()
    db_session.execute(
        user_roles_table.insert().values(user_id=actor.id, role_id=qc_role.id)
    )
    db_session.commit()
    patient_id, actor_id = patient.id, actor.id

    template = service.create_template({
        "code": "synthetic_shadow",
        "name": "SYNTHETIC shadow report",
        "family": "synthetic",
        "initial_version": {
            "layout_preset": "lab_table_classic_v1",
            "sections": [{
                "key": "synthetic",
                "fields": [
                    {
                        "field_key": FIELD_KEY,
                        "label": "SYNTHETIC result",
                        "value_type": "numeric",
                        "required": False,
                        "reference_mode": "static_text",
                        "reference_text": "1 - 2",
                        "highlight_rule": {
                            "mode": "range", "low": 1, "high": 2, "critical_high": 3,
                        },
                    },
                    {
                        "field_key": HIDDEN_FIELD_KEY,
                        "label": "SYNTHETIC conditional result",
                        "value_type": "text",
                        "required": False,
                        "visibility_rule": {
                            "source": f"field.{FIELD_KEY}", "op": "gt", "value": 100,
                        },
                    },
                ],
            }],
        },
    })
    template_version = service.publish_template_version(template.versions[0].id)
    template_id, template_version_id = template.id, template_version.id

    def create(*, value="1.5", absent=False, hidden=False, qc="accepted", submit=True):
        report = service.create_instance(
            {
                "patient_id": patient_id,
                "template_id": template_id,
                "template_version_id": template_version_id,
            },
            actor_user_id=actor_id,
        )
        specimen = LabSpecimen(
            order_id=report.order_id,
            barcode="SYNTHETIC-SHADOW",
            material_code="synthetic-material",
            container_code="synthetic-container",
            status="accepted",
            revision=4,
            create_request_id=str(uuid4()),
            created_at=datetime.now(UTC),
        )
        db_session.add(specimen)
        db_session.flush()
        db_session.add(
            LabSpecimenAssignment(specimen_id=specimen.id, report_instance_id=report.id)
        )
        db_session.commit()

        report_id = report.id
        result = (
            {"result_kind": "absent", "absence_reason": "SYNTHETIC"}
            if absent else {"value_text": value}
        )
        values = [{"field_key": FIELD_KEY, **result}]
        if hidden:
            values.append({"field_key": HIDDEN_FIELD_KEY, "value_text": "SYNTHETIC"})
        report, _ = service.bulk_upsert_values(
            report_id,
            values,
            expected_updated_at=report.updated_at.isoformat(),
            actor_user_id=actor_id,
        )
        if qc is not None:
            report = service.record_report_qc(
                report_id,
                actor_user_id=actor_id,
                command=LabReportQCIn(
                    expected_updated_at=report.updated_at.isoformat(),
                    status=qc,
                    reason="SYNTHETIC disposition",
                    method="SYNTHETIC",
                    series_ref="SYNTHETIC-QC",
                ),
            )
        if submit:
            report = service.submit_for_review(
                report_id,
                actor_user_id=actor_id,
                expected_updated_at=report.updated_at.isoformat(),
            )
        return report, specimen

    return create


def _rules(report, *, field_key=FIELD_KEY, method_code=None, template_version_id=None):
    return ShadowRuleSet(
        version="synthetic-shadow-v1",
        review_reference="SYNTHETIC-SHADOW-REVIEW",
        template_version_id=template_version_id or report.template_version_id,
        fields=(ShadowFieldRule(
            field_key=field_key,
            result_kind="numeric",
            interpretation="normal",
            method_code=method_code,
            unit_code=None,
        ),),
    )


def _evidence(
    report, *, instrument_warnings="clear", unusual_change="clear", report_version=None,
):
    return ShadowEvidence(
        instance_id=report.id,
        report_version=report_version or report.updated_at.replace(tzinfo=UTC),
        instrument_warnings=instrument_warnings,
        unusual_change=unusual_change,
    )


def _evaluate(service, report, rules=None, evidence=None, *, version=None):
    return evaluate_autoverification_shadow(
        service,
        report.id,
        expected_updated_at=version or report.updated_at.isoformat(),
        rules=rules,
        evidence=evidence,
    )


def test_shadow_is_disabled_by_default_and_requires_a_ruleset(
    shadow_service, make_report, monkeypatch,
):
    assert Settings.model_fields["LAB_AUTOVERIFICATION_SHADOW_ENABLED"].default is False
    report, _ = make_report()
    monkeypatch.setattr(settings, "LAB_AUTOVERIFICATION_SHADOW_ENABLED", False)
    assert (
        _evaluate(shadow_service, report, _rules(report), _evidence(report)).status
        == "disabled"
    )
    monkeypatch.setattr(settings, "LAB_AUTOVERIFICATION_SHADOW_ENABLED", True)
    assert (
        _evaluate(shadow_service, report, evidence=_evidence(report)).status
        == "unconfigured"
    )


def test_shadow_rules_reject_missing_provenance_and_duplicate_fields():
    field = ShadowFieldRule(
        field_key=FIELD_KEY,
        result_kind="numeric",
        interpretation="normal",
        method_code=None,
        unit_code=None,
    )
    with pytest.raises(ValidationError, match="review_reference"):
        ShadowRuleSet(
            version="synthetic-shadow-v1", review_reference="",
            template_version_id=1, fields=(field,),
        )
    with pytest.raises(ValidationError, match="field keys must be unique"):
        ShadowRuleSet(
            version="synthetic-shadow-v1",
            review_reference="SYNTHETIC-SHADOW-REVIEW",
            template_version_id=1,
            fields=(field, field),
        )


def test_shadow_match_leaves_report_events_and_audit_untouched(
    shadow_service, make_report, db_session,
):
    report, _ = make_report()
    assert report.status == "IN_REVIEW"
    assert shadow_service.report_release_holds(report) == []
    report_id = report.id
    version = report.updated_at
    signer = deepcopy(report.signer_snapshot)
    values = deepcopy(shadow_service.materialize_instance(report))
    history_ids = [event.id for event in shadow_service.workflow_history(report_id)]
    audit_ids = [
        event.id for event in audit_crud.list_logs(
            db_session, entity_type="lab_report", entity_id=report_id,
        )
    ]

    rules = _rules(report)
    offset_version = version.replace(tzinfo=UTC).astimezone(
        timezone(timedelta(hours=5)),
    )
    decision = _evaluate(
        shadow_service, report, rules, _evidence(report, report_version=offset_version),
        version=offset_version.isoformat(),
    )

    assert decision.status == "shadow_match"
    assert decision.reasons == ()
    assert decision.ruleset_version == rules.version
    assert decision.report_version.replace(tzinfo=UTC) == version.replace(tzinfo=UTC)
    assert not db_session.new
    assert not db_session.dirty
    assert not db_session.deleted
    db_session.expire_all()
    saved = shadow_service.get_instance(report_id)
    assert (saved.status, saved.updated_at, saved.finalized_at) == (
        "IN_REVIEW", version, None,
    )
    assert saved.signer_snapshot == signer
    assert shadow_service.materialize_instance(saved) == values
    assert [
        event.id for event in shadow_service.workflow_history(report_id)
    ] == history_ids
    assert [
        event.id for event in audit_crud.list_logs(
            db_session, entity_type="lab_report", entity_id=report_id,
        )
    ] == audit_ids


def test_shadow_preserves_uncommitted_changes(shadow_service, make_report, db_session):
    report, _ = make_report()
    report_id = report.id
    original_signers = deepcopy(report.signer_snapshot)
    rules = _rules(report)
    evidence = _evidence(report)
    report.signer_snapshot = {"lab_technician_name": "SYNTHETIC uncommitted"}

    decision = _evaluate(shadow_service, report, rules, evidence)

    assert decision.status == "manual_review"
    assert decision.reasons == ("uncommitted_context",)
    assert report.signer_snapshot == {"lab_technician_name": "SYNTHETIC uncommitted"}
    assert db_session.is_modified(report)
    db_session.rollback()
    assert shadow_service.get_instance(report_id).signer_snapshot == original_signers


@pytest.mark.parametrize(("field", "status", "reason"), [
    ("instrument_warnings", "unknown", "instrument_warning_evidence_missing"),
    ("instrument_warnings", "hold", "instrument_warning"),
    ("unusual_change", "unknown", "unusual_change_evidence_missing"),
    ("unusual_change", "hold", "unusual_change"),
])
def test_shadow_fails_closed_on_unknown_or_held_evidence(
    shadow_service, make_report, field, status, reason,
):
    report, _ = make_report()
    decision = _evaluate(
        shadow_service, report, _rules(report), _evidence(report, **{field: status}),
    )
    assert decision.status == "manual_review"
    assert reason in decision.reasons


def test_shadow_reports_stored_instrument_warning_with_clear_caller_evidence(
    shadow_service, make_report, db_session,
):
    report, _ = make_report()
    value = report.values[0]
    value.result_payload = {
        **value.result_payload,
        "import_origin": {
            "source": "csv",
            "message_id": str(uuid4()),
            "submitted_analyte_code": FIELD_KEY,
            "instrument_flags": ["SYNTHETIC_FLAG"],
        },
    }
    db_session.commit()

    decision = _evaluate(shadow_service, report, _rules(report), _evidence(report))

    assert decision.status == "manual_review"
    assert "instrument_warning" in decision.reasons


def test_shadow_checks_report_rules_and_evidence_versions(shadow_service, make_report):
    report, _ = make_report()
    earlier = report.updated_at.replace(tzinfo=UTC) - timedelta(seconds=1)
    rules = _rules(report)
    evidence = _evidence(report)
    wrong_template_rules = _rules(report, template_version_id=report.template_version_id + 1)
    cases = [
        (
            _evaluate(shadow_service, report, rules, evidence, version=earlier.isoformat()),
            "report_version_changed",
        ),
        (_evaluate(shadow_service, report, rules), "evidence_missing"),
        (
            _evaluate(shadow_service, report, rules, _evidence(report, report_version=earlier)),
            "evidence_version_mismatch",
        ),
        (
            _evaluate(shadow_service, report, wrong_template_rules, evidence),
            "ruleset_template_version_mismatch",
        ),
    ]
    for decision, reason in cases:
        assert decision.status == "manual_review"
        assert reason in decision.reasons


def test_shadow_keeps_drafts_outside_review(shadow_service, make_report):
    report, _ = make_report(submit=False)
    decision = _evaluate(shadow_service, report, _rules(report), _evidence(report))
    assert decision.status == "manual_review"
    assert "report_not_in_review" in decision.reasons


@pytest.mark.parametrize(("result_options", "rule_options", "reason"), [
    ({}, {"field_key": "uncovered_synthetic_field"}, "result_rule_coverage_mismatch"),
    ({}, {"method_code": "SYNTHETIC-MISMATCH"}, "result_rule_mismatch"),
    ({"absent": True}, {}, "result_evaluation_unavailable"),
    ({"value": "4"}, {}, "critical_result"),
])
def test_shadow_requires_an_evaluated_covered_result(
    shadow_service, make_report, result_options, rule_options, reason,
):
    report, _ = make_report(**result_options)
    decision = _evaluate(
        shadow_service, report, _rules(report, **rule_options), _evidence(report),
    )
    assert decision.status == "manual_review"
    assert reason in decision.reasons


def test_shadow_checks_coverage_of_populated_hidden_results(shadow_service, make_report):
    report, _ = make_report(hidden=True)
    assert {value.field_key for value in report.values} == {FIELD_KEY, HIDDEN_FIELD_KEY}
    assert {
        field["field_key"]
        for section in shadow_service.materialize_instance(report)
        for field in section["fields"]
    } == {FIELD_KEY}

    decision = _evaluate(shadow_service, report, _rules(report), _evidence(report))

    assert decision.status == "manual_review"
    assert "result_rule_coverage_mismatch" in decision.reasons


@pytest.mark.parametrize(("qc", "reason"), [
    (None, "qc_missing"), ("rejected", "qc_rejected"),
])
def test_shadow_preserves_native_qc_holds(shadow_service, make_report, qc, reason):
    report, _ = make_report(qc=qc)
    assert reason in shadow_service.report_release_holds(report)
    decision = _evaluate(shadow_service, report, _rules(report), _evidence(report))
    assert decision.status == "manual_review"
    assert reason in decision.reasons


def test_shadow_honors_changed_specimen_evidence(shadow_service, make_report, db_session):
    report, specimen = make_report()
    specimen.revision += 1
    db_session.commit()
    decision = _evaluate(shadow_service, report, _rules(report), _evidence(report))
    assert decision.status == "manual_review"
    assert "review_evidence_changed" in decision.reasons
