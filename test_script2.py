import re

def _missing_required_field_answers(section: str, text: str) -> list[str]:
    REQUIRED_FIELDS_BY_SECTION = {
        "Cyclic Execution Evidence": (
            "Fresh main sync",
            "Clean workspace",
            "Branch",
            "Scope gate",
            "Red-check handling",
        ),
    }

    required_fields = REQUIRED_FIELDS_BY_SECTION.get(section, ())
    if not required_fields:
        return []

    FIELD_RE = re.compile(r"^[ \t]*-[ \t]*([^:\n]+):[ \t]*(.*?)[ \t]*$", re.MULTILINE)

    def _strip_guidance_lines(text: str) -> str:
        return text.strip()

    def _has_not_applicable_reason(text: str) -> bool:
        match = re.search(r"\bnot applicable\b\s*(?:[-:;,]|\sbecause\b)\s*(.+)", text, re.I)
        if not match:
            return False
        reason = match.group(1).strip()
        return len(reason.split()) >= 3

    cleaned = _strip_guidance_lines(text)
    field_pairs = FIELD_RE.findall(cleaned)
    if not field_pairs and _has_not_applicable_reason(cleaned):
        return []

    fields = {name.strip().lower(): value.strip() for name, value in field_pairs}
    missing: list[str] = []

    for field in required_fields:
        value = fields.get(field.lower(), "")
        if not value or value.lower() == "n/a":
            missing.append(field)
            continue
        if value.lower() == "not applicable" or (
            value.lower().startswith("not applicable") and not _has_not_applicable_reason(value)
        ):
            missing.append(field)

    return missing

print("Test:", _missing_required_field_answers("Cyclic Execution Evidence", "not applicable - purely visual UI component change that does not interact with the system architecture"))
