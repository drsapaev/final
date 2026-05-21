# Global Icon-Only Controls Accessibility Sweep

Date: 2026-05-21

## Scope

- Frontend source only: `frontend/src/**/*.{js,jsx,ts,tsx}`
- Excludes tests, mocks, build output, and `node_modules`
- Audited controls:
  - native `button`
  - elements with interactive roles such as `role="button"`, `role="tab"`, and `role="switch"`
- Required accessible-name sources:
  - `aria-label`
  - `aria-labelledby`
  - visible text
  - screen-reader-only text components such as `VisuallyHidden`

## Result

Command:

```powershell
cd frontend
npm run audit:icon-controls
```

Result:

```text
Files scanned: 614
Findings: 200
Parse errors: 0
Baseline entries: 200
New findings: 0
Stale baseline entries: 0
```

The project now has a required no-new-regression gate for icon-only controls. The current historical baseline is tracked in `frontend/scripts/a11y/icon-only-controls-baseline.json`.

## Cleanup Progress

- 2026-05-21: chat and AI controls cleanup removed 18 baseline findings.
- 2026-05-21: payment and cashier controls cleanup removed 6 baseline findings.
- 2026-05-21: runtime queue controls cleanup removed 9 baseline findings.
- 2026-05-21: admin queue configuration controls cleanup removed 11 baseline findings.
- 2026-05-21: admin security and QR controls cleanup removed 7 baseline findings.
- 2026-05-21: file manager controls cleanup removed 11 baseline findings.
- 2026-05-21: doctor panel primary controls cleanup removed 12 baseline findings.
- 2026-05-21: doctor panel queue and modal controls cleanup removed 9 baseline findings.
- 2026-05-21: EMR v2 controls cleanup removed 12 baseline findings.
- 2026-05-21: dermatology controls cleanup removed 13 baseline findings.
- 2026-05-21: dental photo archive controls cleanup removed 13 baseline findings.
- 2026-05-21: dental diagnosis form controls cleanup removed 7 baseline findings.
- 2026-05-21: dental visit protocol controls cleanup removed 7 baseline findings.
- 2026-05-21: dental examination form controls cleanup removed 5 baseline findings.
- 2026-05-21: dental protocol template controls cleanup removed 5 baseline findings.
- 2026-05-21: dental chart controls cleanup removed 4 baseline findings.
- 2026-05-21: dental patient card controls cleanup removed 4 baseline findings.
- 2026-05-21: dental teeth chart controls cleanup removed 3 baseline findings.
- 2026-05-21: remaining dental close controls cleanup removed 4 baseline findings.
- 2026-05-21: two-factor security controls cleanup removed 7 baseline findings.
- 2026-05-21: auth password controls cleanup removed 6 baseline findings.
- 2026-05-21: notification template controls cleanup removed 4 baseline findings.
- 2026-05-21: display board controls cleanup removed 3 baseline findings.
- 2026-05-21: medical table controls cleanup removed 3 baseline findings.
- Current baseline after this slice: 17 findings.

## CI Policy

- `npm run audit:icon-controls` fails when new icon-only controls are added without a robust accessible name.
- `npm run audit:icon-controls:strict` fails on any finding and is the target command after baseline cleanup.
- The CI `frontend-lint` job runs the baseline-gated sweep after `npm run lint:check`.

## Baseline Cleanup Backlog

Priority cleanup order:

1. Chat and AI controls: `frontend/src/components/chat/**`, `frontend/src/components/ai/**`
2. Payment and cashier controls: `frontend/src/components/payment/**`, `frontend/src/components/cashier/**`
3. Queue controls: `frontend/src/components/queue/**`, `frontend/src/components/admin/Queue*.jsx`
4. Doctor and EMR controls: `frontend/src/pages/DoctorPanel.jsx`, `frontend/src/components/emr-v2/**`
5. Specialty panels: dental and dermatology controls
6. Shared UI primitives: native modal, switch, floating action button, table controls

## Notes

- `title` alone is intentionally treated as insufficient for icon-only controls.
- Existing baseline debt is not hidden: it is tracked explicitly and should shrink with each targeted cleanup PR.
- Protected clinical/payment/queue flows should be browser-checked before deleting baseline entries for those surfaces.
