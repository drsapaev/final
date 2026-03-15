# W1.9-T4 jsPDF Critical Dependency Decision

Date: 2026-03-06  
Branch: `codex/w19-gate-blockers`  
Status: `done`

## Current State

From `npm ls`:
- `jspdf@3.0.2`
- `jspdf-autotable@5.0.7`

From `npm audit`:
- `jspdf` remains `critical`
- fix path proposes `jspdf@4.2.0` (major upgrade)

## Usage Impact Check

Primary usage path reviewed:
- `frontend/src/components/laboratory/LabReportGenerator.jsx`

Observed usage pattern:
- `new jsPDF()`
- `doc.text(...)`
- `doc.autoTable(...)`
- `doc.save(...)`

No direct `addJS` usage observed in this component.

## Decision Options Assessment

1. Upgrade to `4.x` now  
Result: high regression risk in PDF output behavior; requires dedicated compatibility testing slice.

2. Safe temporary mitigation  
Result: viable for Wave 1.9 bounded scope.

3. Defer to Wave 2  
Result: required for major upgrade execution planning.

## Selected Decision

Selected: **2 + 3**
- Apply temporary mitigation stance now.
- Defer major upgrade execution to a dedicated Wave 2 bounded task.

## Mitigation Baseline Until Upgrade

1. Keep PDF generation paths limited to text/table rendering patterns.
2. Forbid introducing dynamic PDF JavaScript features.
3. Treat all report fields as untrusted input and keep normalization/length bounds.
4. Preserve explicit tracking of this dependency as unresolved critical risk.

## Gate Impact

- Risk reduced operationally but not eliminated.
- `jspdf` remains an unresolved critical dependency until major upgrade + regression proof is completed.

