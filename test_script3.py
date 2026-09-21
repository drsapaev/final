import re

def validate_pr_body(body: str):
    REQUIRED_SECTIONS = (
        "Summary",
        "Cyclic Execution Evidence",
        "Contract Impact",
        "RBAC / Permissions",
        "Notification / Realtime",
        "Frontend Resilience",
        "Scope Gate",
        "Validation",
    )

    REQUIRED_FIELDS_BY_SECTION = {
        "Cyclic Execution Evidence": (
            "Fresh main sync",
            "Clean workspace",
            "Branch",
            "Scope gate",
            "Red-check handling",
        ),
        "Contract Impact": (
            "Canonical surface",
            "Request shape",
            "Response shape",
            "Status codes",
            "Frontend consumer",
            "Compatibility path or alias",
            "Contract proof",
        ),
        "RBAC / Permissions": (
            "Roles allowed",
            "Roles denied",
            "Positive auth proof",
            "Negative auth proof",
        ),
        "Notification / Realtime": (
            "Event type or websocket channel",
            "Payload version / ack behavior",
            "Read/unread or delivery semantics",
            "Reconnect/resync proof",
        ),
        "Frontend Resilience": (
            "Empty data proof",
            "Partial data proof",
            "Forbidden secondary path behavior",
            "Missing draft/resource behavior",
            "Stale route/deep-link behavior",
        ),
        "Scope Gate": (
            "Allowed paths",
            "Denied paths",
            "Migration/docs/test impact",
            "Rollback note",
        ),
        "Validation": (
            "Targeted tests or smoke run",
            "Result",
            "Not checked",
        ),
    }

    HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
    FIELD_RE = re.compile(r"^[ \t]*-[ \t]*([^:\n]+):[ \t]*(.*?)[ \t]*$", re.MULTILINE)

    def _extract_sections(body: str) -> dict[str, str]:
        matches = list(HEADING_RE.finditer(body))
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            title = match.group(1).strip()
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            sections[title] = body[start:end].strip()
        return sections

    def _strip_guidance_lines(text: str) -> str:
        return text.strip()

    def _has_not_applicable_reason(text: str) -> bool:
        match = re.search(r"\bnot applicable\b\s*(?:[-:;,]|\sbecause\b)\s*(.+)", text, re.I)
        if not match:
            return False
        reason = match.group(1).strip()
        return len(reason.split()) >= 3

    def _missing_required_field_answers(section: str, text: str) -> list[str]:
        required_fields = REQUIRED_FIELDS_BY_SECTION.get(section, ())
        if not required_fields:
            return []

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

    sections = _extract_sections(body)
    errors = []

    for required in REQUIRED_SECTIONS:
        if required not in sections:
            errors.append(f"Missing required section: ## {required}")
            continue
        missing_fields = _missing_required_field_answers(required, sections[required])
        if missing_fields:
            errors.append(
                f"Section ## {required} has unanswered required fields: "
                + ", ".join(missing_fields)
            )

    print("Errors:", errors)
    return errors

body = """
## Summary
🎨 Palette: Added loading indicator to file uploader

💡 **What:** Added a `Loader2` spinning icon (from `lucide-react`) to the file upload button in `FileUploader.tsx` while a file is being validated asynchronously. Added `aria-hidden="true"` to the decorative icons to hide them from screen readers.
🎯 **Why:** Async file validation (like magic-number MIME type checks to prevent malicious uploads) can take time. Without a loading indicator, the file uploader button appears frozen and unresponsive. The `aria-hidden` prevents redundant screen reader announcements since the button itself has an `aria-label`.
📸 **Before/After:** Before, the button remained static during validation. After, it shows a spinning loader icon.
♿ **Accessibility:** Added `aria-hidden="true"` to the `Paperclip` and `Loader2` icons within the button since the button already has a descriptive `aria-label`.

## Cyclic Execution Evidence
Not applicable - purely visual UI component change that does not interact with the system architecture

## Contract Impact
Not applicable - purely visual UI component change that does not affect data contracts

## RBAC / Permissions
Not applicable - purely visual UI component change that does not affect permissions

## Notification / Realtime
Not applicable - purely visual UI component change that does not affect notifications

## Frontend Resilience
Not applicable - purely visual UI component change that does not affect resilience

## Scope Gate
Not applicable - purely visual UI component change that does not affect scope gate

## Validation
Not applicable - purely visual UI component change, validated visually
"""

validate_pr_body(body)
