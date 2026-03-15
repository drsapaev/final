# W1.75 jsPDF Risk Decision

Date: 2026-03-06  
Branch: `codex/w175-gate-readiness`  
Status: `done`

## Current Version

From `npm ls`:
- `jspdf@3.0.2`
- `jspdf-autotable@5.0.7`

## Vulnerability Context

`npm audit` reports `jspdf` as `critical` (plus multiple high advisories), including:
- local file inclusion/path traversal class issue
- PDF injection/arbitrary JavaScript execution class issues
- malformed image DoS class issues

Audit fix path points to:
- `jspdf@4.2.0` (semver major)

## Runtime Usage in Repository

Primary observed usage:
- `frontend/src/components/laboratory/LabReportGenerator.jsx`
- usage pattern in this component is text/table PDF generation (`new jsPDF()`, `autoTable`, `text`, `save`).

No direct `addJS` call is present in this component.

## Possible Consequences If Unaddressed

1. Crafted input or downstream plugin behavior could expose PDF injection risks.
2. Malicious or malformed payloads may trigger client-side resource abuse during PDF generation workflows.
3. Critical severity remains a policy/gate concern even when exploitability is context-dependent.

## Decision

Selected option: **2 — safe temporary mitigation**

Rationale:
- Immediate major upgrade (`4.2.0`) is likely to require compatibility/regression validation and can break existing PDF flows.
- Current Wave 1.75 scope explicitly avoids large dependency/architecture changes.

## Temporary Mitigation Set (now)

1. Treat all PDF text fields as untrusted and normalize/limit input length.
2. Keep PDF generation usage constrained to text/table operations.
3. Forbid adding dynamic JS payload features in PDF generation flows.
4. Preserve explicit tracking as unresolved critical dependency risk.

## Required Follow-up

- Schedule dedicated bounded slice to evaluate `jspdf` major upgrade with regression tests for:
  - laboratory report PDF layout
  - generated file integrity
  - user-visible content fidelity

Decision impact on gate:
- Risk is **not closed**; mitigation is temporary and must be tracked in Wave 2 entry criteria.
