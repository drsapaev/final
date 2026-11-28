import pytest

from app.services.lab_clinical_configuration_service import (
    ClinicalConfigurationError,
    approve_version,
    create_draft,
    normalize_configuration_snapshot,
    submit_for_approval,
    update_draft,
)
from app.models.user import User


@pytest.fixture
def valid_clinical_snapshot():
    return {
        "method_instructions": [
            {
                "method_code": "SYNTHETIC-METHOD",
                "method_version": "SYNTHETIC-1",
                "language_code": "en",
                "instruction_text": "Synthetic method instruction for contract coverage.",
                "source_ref": "clinic-document://synthetic/method-1",
            }
        ],
        "reference_intervals": [
            {
                "rule_code": "SYNTHETIC-RANGE-1",
                "analyte_code": "SYNTHETIC-ANALYTE",
                "method_code": "SYNTHETIC-METHOD",
                "unit_code": "synthetic_unit",
                "age_min_months": 0,
                "age_max_months": 1200,
                "low": 1.0,
                "high": 10.0,
                "critical_low": 0.5,
                "critical_high": 12.0,
                "source_ref": "clinic-document://synthetic/reference-1",
            }
        ],
        "critical_values": [],
        "qc_rules": [],
        "not_applicable_reasons": {
            "critical_values": "No separate critical threshold in this synthetic profile.",
            "qc_rules": "No instrument-specific QC rule in this synthetic profile.",
        },
    }


@pytest.mark.unit
def test_clinical_snapshot_preserves_versioned_sections_and_explicit_dispositions(
    valid_clinical_snapshot,
):
    normalized = normalize_configuration_snapshot(valid_clinical_snapshot)

    assert normalized["method_instructions"][0]["method_version"] == "SYNTHETIC-1"
    assert normalized["reference_intervals"][0]["critical_high"] == 12.0
    assert set(normalized["not_applicable_reasons"]) == {"critical_values", "qc_rules"}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda snapshot: snapshot["reference_intervals"][0].update(low=11.0, high=10.0),
            "invalid_configuration_snapshot",
        ),
        (
            lambda snapshot: snapshot["reference_intervals"][0].update(age_min_months=-1),
            "invalid_configuration_snapshot",
        ),
        (
            lambda snapshot: snapshot["method_instructions"][0].update(source_ref=""),
            "clinical_source_reference_required",
        ),
        (
            lambda snapshot: snapshot["qc_rules"].append(
                {
                    "rule_code": "SYNTHETIC-QC-1",
                    "method_code": "SYNTHETIC-METHOD",
                    "rule_type": "synthetic",
                    "configuration": {"limit": float("nan")},
                    "source_ref": "clinic-document://synthetic/qc-1",
                }
            ),
            "invalid_configuration_snapshot",
        ),
        (
            lambda snapshot: snapshot.update(patient_id=123),
            "sensitive_configuration_field_forbidden",
        ),
    ],
)
def test_invalid_or_sensitive_clinical_configuration_is_rejected(
    valid_clinical_snapshot, mutate, code
):
    mutate(valid_clinical_snapshot)
    with pytest.raises(ClinicalConfigurationError) as error:
        normalize_configuration_snapshot(valid_clinical_snapshot)
    assert error.value.code == code


@pytest.mark.unit
def test_unconfigured_clinical_sections_are_not_silently_marked_not_applicable():
    normalized = normalize_configuration_snapshot({})
    assert normalized["method_instructions"] == []
    assert normalized["reference_intervals"] == []
    assert normalized["not_applicable_reasons"] == {}


@pytest.mark.unit
def test_clinical_configuration_lifecycle_uses_assigned_primary_and_substitute(
    db_session, valid_clinical_snapshot
):
    admin = User(
        username="synthetic_clinical_admin",
        hashed_password="not-used-by-test",
        role="Admin",
        is_active=True,
    )
    primary = User(
        username="synthetic_clinical_primary",
        hashed_password="not-used-by-test",
        role="Lab",
        is_active=True,
    )
    substitute = User(
        username="synthetic_clinical_substitute",
        hashed_password="not-used-by-test",
        role="Lab",
        is_active=True,
    )
    db_session.add_all([admin, primary, substitute])
    db_session.commit()

    first = create_draft(
        db_session,
        configuration_snapshot=valid_clinical_snapshot,
        primary_lab_physician_user_id=primary.id,
        substitute_lab_physician_user_id=substitute.id,
        actor=admin,
    )
    submitted = submit_for_approval(db_session, version_id=first.id, actor=admin)
    assert submitted.status == "PENDING_APPROVAL"

    with pytest.raises(ClinicalConfigurationError) as error:
        approve_version(db_session, version_id=first.id, actor=admin)
    assert error.value.code == "lab_physician_approval_required"

    approved = approve_version(db_session, version_id=first.id, actor=primary)
    assert approved.status == "APPROVED"
    assert approved.approval_authority_snapshot["assignment"] == "primary"

    second = create_draft(
        db_session,
        configuration_snapshot=valid_clinical_snapshot,
        primary_lab_physician_user_id=primary.id,
        substitute_lab_physician_user_id=substitute.id,
        actor=admin,
    )
    submit_for_approval(db_session, version_id=second.id, actor=admin)
    approved_second = approve_version(db_session, version_id=second.id, actor=substitute)
    assert approved_second.status == "APPROVED"
    assert approved_second.approval_authority_snapshot["assignment"] == "substitute"
    db_session.refresh(first)
    assert first.status == "ARCHIVED"

    with pytest.raises(ClinicalConfigurationError) as immutable_error:
        update_draft(
            db_session,
            version_id=first.id,
            configuration_snapshot=valid_clinical_snapshot,
            primary_lab_physician_user_id=primary.id,
            substitute_lab_physician_user_id=substitute.id,
            actor=admin,
        )
    assert immutable_error.value.code == "configuration_version_not_draft"
