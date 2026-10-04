import re

text = """
## Validation
- Targeted tests or smoke run: Ran `pnpm lint:check` and `pnpm test --run src/components/ui/macos/__tests__/`. Also ran `node scripts/audit-icon-only-controls.mjs --root src/ --include-components`
- Result: All tests passed
- Not checked: None
"""

FIELD_RE = re.compile(r"^[ \t]*-[ \t]*([^:\n]+):[ \t]*(.*?)[ \t]*$", re.MULTILINE)

def _has_not_applicable_reason(text: str) -> bool:
    cleaned = text.strip()
    match = re.search(r"\bnot applicable\b\s*(?:[-:;,]|\sbecause\b)\s*(.+)", cleaned, re.I)
    if not match:
        return False
    reason = match.group(1).strip()
    return len(reason.split()) >= 3

REQUIRED_FIELDS_BY_SECTION = {
    "Validation": (
        "Targeted tests or smoke run",
        "Result",
        "Not checked",
    ),
}

section = "Validation"
required_fields = REQUIRED_FIELDS_BY_SECTION.get(section, ())

cleaned = text
field_pairs = FIELD_RE.findall(cleaned)
if not field_pairs and _has_not_applicable_reason(cleaned):
    print("Has not applicable reason")

fields = {name.strip().lower(): value.strip() for name, value in field_pairs}
missing = []

print("fields:", fields)

for field in required_fields:
    value = fields.get(field.lower(), "")
    print(f"checking {field}, value: '{value}'")
    if not value or value.lower() == "n/a":
        missing.append(field)
        continue
    if value.lower() == "not applicable" or (
        value.lower().startswith("not applicable") and not _has_not_applicable_reason(value)
    ):
        missing.append(field)

print("Missing:", missing)
