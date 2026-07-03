"""Canonical EMR v2 contract helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

CANONICAL_SPECIALTIES = {
    "general",
    "cardiology",
    "dermatology",
    "dentistry",
    "lab",
}

SPECIALTY_ALIASES = {
    "": "general",
    "doctor": "general",
    "general_medicine": "general",
    "therapy": "general",
    "cardio": "cardiology",
    "cardiologist": "cardiology",
    "derma": "dermatology",
    "dermatologist": "dermatology",
    "dentist": "dentistry",
    "dental": "dentistry",
    "stomatology": "dentistry",
    "stomatologist": "dentistry",
    "laboratory": "lab",
    "laboratoriya": "lab",
}

SPECIALTY_SKELETONS: dict[str, dict[str, Any]] = {
    "general": {},
    "cardiology": {
        "ecg": {},
        "echo": {},
        "cardio_labs": {},
    },
    "dermatology": {
        "photos": [],
        "skin_type": "",
        "conditions": [],
        "localization": {},
    },
    "dentistry": {
        "tooth_status": {},
        "hygiene_indices": {},
        "periodontal_pockets": {},
        "measurements": {},
        "radiographs": {},
    },
    "lab": {
        "results": [],
        "references": [],
        "clinician_interpretation": "",
        "signed_snapshot": {},
    },
}


def normalize_specialty(value: str | None, *, default: str = "general") -> str:
    """Normalize any specialty alias into the canonical taxonomy."""
    normalized_default = default.strip().lower() if isinstance(default, str) else "general"
    normalized_default = SPECIALTY_ALIASES.get(normalized_default, normalized_default)
    if normalized_default not in CANONICAL_SPECIALTIES:
        normalized_default = "general"

    raw = (value or "").strip().lower()
    if not raw:
        return normalized_default
    if raw in CANONICAL_SPECIALTIES:
        return raw
    if raw in SPECIALTY_ALIASES:
        return SPECIALTY_ALIASES[raw]
    return normalized_default


def build_specialty_skeleton(specialty: str) -> dict[str, Any]:
    """Return a deep-copied specialty skeleton for new EMRs."""
    canonical = normalize_specialty(specialty)
    return deepcopy(SPECIALTY_SKELETONS.get(canonical, {}))


def normalize_specialty_data(
    specialty: str,
    specialty_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge the specialty skeleton with provided data."""
    skeleton = build_specialty_skeleton(specialty)
    if not isinstance(specialty_data, dict):
        return skeleton

    merged = skeleton
    for key, value in specialty_data.items():
        merged[key] = value
    return merged


def normalize_emr_data(
    data: dict[str, Any] | None,
    *,
    fallback_specialty: str | None = None,
) -> dict[str, Any]:
    """Guarantee required v2 keys and canonical specialty."""
    payload = deepcopy(data) if isinstance(data, dict) else {}
    specialty = normalize_specialty(
        payload.get("specialty"),
        default=fallback_specialty or "general",
    )
    payload["specialty"] = specialty
    payload["specialty_data"] = normalize_specialty_data(
        specialty,
        payload.get("specialty_data"),
    )
    return payload


def extract_diagnosis_main(data: dict[str, Any] | None) -> str | None:
    """Get a human-readable diagnosis from EMR JSON."""
    if not isinstance(data, dict):
        return None

    diagnosis = data.get("diagnosis")
    if isinstance(diagnosis, dict):
        main = diagnosis.get("main")
        return main[:500] if isinstance(main, str) and main else None
    if isinstance(diagnosis, str) and diagnosis.strip():
        return diagnosis[:500]

    diagnosis_main = data.get("diagnosis_main")
    if isinstance(diagnosis_main, str) and diagnosis_main.strip():
        return diagnosis_main[:500]
    return None


def extract_icd10_code(data: dict[str, Any] | None) -> str | None:
    """Get ICD-10 from either the structured diagnosis or flat payload."""
    if not isinstance(data, dict):
        return None

    diagnosis = data.get("diagnosis")
    if isinstance(diagnosis, dict):
        code = diagnosis.get("icd10_code") or diagnosis.get("icd_10_code")
        if isinstance(code, str) and code.strip():
            return code[:16]

    code = data.get("icd10_code") or data.get("icd_10_code") or data.get("icd10")
    if isinstance(code, str) and code.strip():
        return code[:16]
    return None


def get_emr_text_field(data: dict[str, Any] | None, field_name: str) -> str:
    """Extract searchable display text for history/AI use."""
    if not isinstance(data, dict):
        return ""

    if field_name == "diagnosis":
        return extract_diagnosis_main(data) or ""

    if field_name == "treatment":
        treatment = data.get("treatment")
        if isinstance(treatment, str) and treatment.strip():
            return treatment
        medications = data.get("medications")
        if isinstance(medications, dict):
            text = medications.get("text")
            if isinstance(text, str) and text.strip():
                return text
        plan = data.get("plan")
        if isinstance(plan, dict):
            plan_treatment = plan.get("treatment")
            if isinstance(plan_treatment, str) and plan_treatment.strip():
                return plan_treatment
        return ""

    value = data.get(field_name)
    if isinstance(value, str):
        return value

    if field_name == "anamnesis_morbi":
        legacy = data.get("anamnesis")
        return legacy if isinstance(legacy, str) else ""

    if field_name == "recommendations":
        recommendations = data.get("recommendations")
        if isinstance(recommendations, str):
            return recommendations
        plan = data.get("plan")
        if isinstance(plan, dict):
            treatment = plan.get("treatment")
            return treatment if isinstance(treatment, str) else ""

    return ""


def legacy_emr_to_v2_data(
    legacy_payload: dict[str, Any],
    *,
    fallback_specialty: str | None = None,
) -> dict[str, Any]:
    """Convert legacy flat EMR payload into the v2 JSON contract."""
    payload = {
        "complaints": legacy_payload.get("complaints") or "",
        "anamnesis_morbi": legacy_payload.get("anamnesis") or "",
        "anamnesis_vitae": legacy_payload.get("social_history") or "",
        "examination": legacy_payload.get("examination") or "",
        "diagnosis": {
            "main": legacy_payload.get("diagnosis") or "",
            "icd10_code": legacy_payload.get("icd10") or "",
            "secondary": [],
        },
        "recommendations": legacy_payload.get("recommendations") or "",
        "vitals": legacy_payload.get("vital_signs") or {},
        "medications": legacy_payload.get("medications") or {},
        "allergies": legacy_payload.get("allergies") or {},
        "family_history": legacy_payload.get("family_history") or {},
        "social_history": legacy_payload.get("social_history") or {},
        "procedures": legacy_payload.get("procedures") or [],
        "attachments": legacy_payload.get("attachments") or [],
        "lab_results": legacy_payload.get("lab_results") or {},
        "imaging_results": legacy_payload.get("imaging_results") or {},
        "notes": legacy_payload.get("notes") or "",
        "template_id": legacy_payload.get("template_id"),
        "ai_suggestions": legacy_payload.get("ai_suggestions") or {},
        "ai_confidence": legacy_payload.get("ai_confidence"),
        "specialty": legacy_payload.get("specialty"),
    }
    return normalize_emr_data(payload, fallback_specialty=fallback_specialty)


def canonical_emr_to_legacy_payload(
    emr_record: Any,
    *,
    appointment_id: int,
) -> dict[str, Any]:
    """Adapt canonical EMR response into the legacy appointment-flow shape."""
    data = normalize_emr_data(getattr(emr_record, "data", None))
    diagnosis = data.get("diagnosis") if isinstance(data.get("diagnosis"), dict) else {}
    return {
        "id": getattr(emr_record, "id", None),
        "appointment_id": appointment_id,
        "complaints": data.get("complaints"),
        "anamnesis": data.get("anamnesis_morbi"),
        "examination": data.get("examination"),
        "diagnosis": diagnosis.get("main") or extract_diagnosis_main(data),
        "icd10": diagnosis.get("icd10_code") or extract_icd10_code(data),
        "recommendations": data.get("recommendations"),
        "procedures": data.get("procedures"),
        "attachments": data.get("attachments"),
        "vital_signs": data.get("vitals"),
        "lab_results": data.get("lab_results"),
        "imaging_results": data.get("imaging_results"),
        "medications": data.get("medications"),
        "allergies": data.get("allergies"),
        "family_history": data.get("family_history"),
        "social_history": data.get("social_history"),
        "ai_suggestions": data.get("ai_suggestions"),
        "ai_confidence": data.get("ai_confidence"),
        "template_id": data.get("template_id"),
        "specialty": data.get("specialty"),
        "is_draft": getattr(emr_record, "status", "draft") == "draft",
        "created_at": getattr(emr_record, "created_at", None),
        "updated_at": getattr(emr_record, "updated_at", None),
        "saved_at": getattr(emr_record, "signed_at", None) or getattr(emr_record, "updated_at", None),
    }
