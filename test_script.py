import re

def _has_not_applicable_reason(text: str) -> bool:
    match = re.search(r"\bnot applicable\b\s*(?:[-:;,]|\sbecause\b)\s*(.+)", text, re.I)
    if not match:
        return False
    reason = match.group(1).strip()
    print("Reason:", reason)
    return len(reason.split()) >= 3

print("Test:", _has_not_applicable_reason("not applicable - purely visual UI component change that does not interact with the system architecture"))
