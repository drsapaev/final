"""Read-only evaluation of a caller's reviewed rules against a submitted report."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings
from app.schemas.lab_reporting import (
    LabInterpretation,
    LabQualitativeCode,
    LabResultComparator,
)
from app.services.lab_reporting._base import LabReportingDomainError

if TYPE_CHECKING:
    from app.services.lab_reporting import LabReportingService


class ShadowFieldRule(BaseModel):
    """An exact match on canonical facts for one field of the published version."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    field_key: str = Field(min_length=1, max_length=64)
    result_kind: Literal["numeric", "qualified_numeric", "coded_qualitative"]
    interpretation: LabInterpretation
    method_code: str | None = Field(min_length=1, max_length=64)
    unit_code: str | None = Field(min_length=1, max_length=32)
    comparator: LabResultComparator | None = None
    qualitative_code: LabQualitativeCode | None = None

    @model_validator(mode="after")
    def check_result_kind(self) -> Self:
        if (self.comparator is not None) != (self.result_kind == "qualified_numeric"):
            raise ValueError("Only qualified numeric rules require a comparator")
        if (self.qualitative_code is not None) != (self.result_kind == "coded_qualitative"):
            raise ValueError("Only coded qualitative rules require a qualitative code")
        return self


class ShadowRuleSet(BaseModel):
    """A trusted caller supplies review provenance and rules for one template version."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    version: str = Field(min_length=1, max_length=80)
    review_reference: str = Field(min_length=1, max_length=120)
    template_version_id: int = Field(gt=0)
    fields: tuple[ShadowFieldRule, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_field_keys(self) -> Self:
        if len({rule.field_key for rule in self.fields}) != len(self.fields):
            raise ValueError("Rule field keys must be unique")
        return self


class ShadowEvidence(BaseModel):
    """Advisory facts verified by the caller for the exact submitted version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    instance_id: int = Field(gt=0)
    report_version: datetime
    instrument_warnings: Literal["clear", "hold", "not_applicable", "unknown"]
    unusual_change: Literal["clear", "hold", "not_applicable", "unknown"]


@dataclass(frozen=True, slots=True)
class ShadowDecision:
    status: Literal["disabled", "unconfigured", "manual_review", "shadow_match"]
    reasons: tuple[str, ...] = ()
    report_version: datetime | None = None
    ruleset_version: str | None = None


def evaluate_autoverification_shadow(
    service: LabReportingService,
    instance_id: int,
    *,
    expected_updated_at: str,
    rules: ShadowRuleSet | None,
    evidence: ShadowEvidence | None,
) -> ShadowDecision:
    """Evaluate one snapshot without writing, logging results or releasing a report.

    The internal caller must establish the ruleset's approval and the evidence's
    provenance. A match is advisory and applies to the returned version only.
    """
    if not settings.LAB_AUTOVERIFICATION_SHADOW_ENABLED:
        return ShadowDecision("disabled")
    if rules is None:
        return ShadowDecision("unconfigured", ("ruleset_missing",))
    if service.db.new or service.db.dirty or service.db.deleted:
        # Refreshing a populated ORM identity would overwrite pending changes.
        return ShadowDecision("manual_review", ("uncommitted_context",), ruleset_version=rules.version)

    with service.db.no_autoflush:
        # The repository's joined read binds the report version and values in one statement.
        report = service.repository.get_instance(instance_id, populate_existing=True)
        if report is None:
            return ShadowDecision("manual_review", ("report_unavailable",), ruleset_version=rules.version)
        report_version = service._normalized_version(report.updated_at)

        def manual_review(*reasons: str) -> ShadowDecision:
            return ShadowDecision("manual_review", reasons, report_version, rules.version)

        if not report.managed_release or report.status != "IN_REVIEW":
            return manual_review("report_not_in_review")
        try:
            expected_version = service._workflow_expected_version(expected_updated_at)
        except LabReportingDomainError:
            return manual_review("report_version_invalid")
        if report_version != expected_version:
            return manual_review("report_version_changed")

        holds = service.report_release_holds(report)
        if holds:
            return manual_review(*holds)
        for value in report.values:
            origin = (value.result_payload or {}).get("import_origin")
            # Any stored flag remains unresolved until a clinic has a disposition policy.
            if origin is not None and (not isinstance(origin, dict) or origin.get("instrument_flags")):
                return manual_review("instrument_warning")
        if rules.template_version_id != report.template_version_id:
            return manual_review("ruleset_template_version_mismatch")
        if evidence is None:
            return manual_review("evidence_missing")
        if (
            evidence.instance_id != instance_id
            or service._normalized_version(evidence.report_version) != report_version
        ):
            return manual_review("evidence_version_mismatch")

        evidence_holds = []
        for status, reason in (
            (evidence.instrument_warnings, "instrument_warning"),
            (evidence.unusual_change, "unusual_change"),
        ):
            if status == "hold":
                evidence_holds.append(reason)
            elif status == "unknown":
                evidence_holds.append(f"{reason}_evidence_missing")
        if evidence_holds:
            return manual_review(*evidence_holds)

        sections = service.materialize_instance(report)
        if service.summarize_critical_findings(sections):
            return manual_review("critical_result")
        fields = [
            field
            for section in sections
            for field in section["fields"]
            if (
                field["required"]
                or field["result_kind"] is not None
                or field["value_text"] is not None
                or field["value_numeric"] is not None
            )
        ]
        stored_result_keys = {
            value.field_key
            for value in report.values
            if value.result_payload or value.value_text is not None or value.value_numeric is not None
        }

    visible_field_keys = [field["field_key"] for field in fields]
    rules_by_key = {rule.field_key: rule for rule in rules.fields}
    # Hidden or unrecognized stored measurements have no visible rule context.
    if (
        sorted(rules_by_key) != sorted(visible_field_keys)
        or not stored_result_keys.issubset(rules_by_key)
    ):
        return manual_review("result_rule_coverage_mismatch")
    for field in fields:
        if field["evaluation_status"] != "evaluated" or field["interpretation"] is None:
            return manual_review("result_evaluation_unavailable")
        rule = rules_by_key[field["field_key"]]
        rule_facts = rule.model_dump(exclude={"field_key"})
        if any(field[name] != value for name, value in rule_facts.items()):
            return manual_review("result_rule_mismatch")

    return ShadowDecision("shadow_match", report_version=report_version, ruleset_version=rules.version)
