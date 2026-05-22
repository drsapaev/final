# Global Icon-Only Controls Accessibility Sweep

Date: 2026-05-21

## Scope

- Frontend source only: `frontend/src/**/*.{js,jsx,ts,tsx}`
- Excludes tests, mocks, build output, and `node_modules`
- Audited controls:
  - native `button`
  - elements with interactive roles such as `role="button"`, `role="tab"`, and `role="switch"`
  - project `Button` and `MacOSButton` components in the component-aware sweep
- Required accessible-name sources:
  - `aria-label`
  - `aria-labelledby`
  - visible text
  - screen-reader-only text components such as `VisuallyHidden`

## Result

Command:

```powershell
cd frontend
npm run audit:icon-controls:strict
```

Result:

```text
Files scanned: 614
Findings: 0
Parse errors: 0
```

The project now has a required strict gate for icon-only controls. The historical baseline in `frontend/scripts/a11y/icon-only-controls-baseline.json` has been reduced to zero entries.

Follow-up component sweep:

```powershell
cd frontend
npm run audit:icon-controls:components
```

Result:

```text
Files scanned: 615
Findings: 127
Baseline entries: 127
New findings: 0
Stale baseline entries: 0
```

The component-aware sweep is now CI-enforced with a separate baseline in `frontend/scripts/a11y/icon-only-component-controls-baseline.json`. This prevents new icon-only `Button`/`MacOSButton` debt while the existing 127 historical component findings are cleaned up in targeted UI slices.

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
- 2026-05-21: appointment wizard controls cleanup removed 3 baseline findings.
- 2026-05-21: schedule next modal controls cleanup removed 2 baseline findings.
- 2026-05-21: shared primitive controls cleanup removed 5 baseline findings.
- 2026-05-21: remaining singleton controls cleanup removed 7 baseline findings.
- Current baseline after this slice: 0 findings.
- 2026-05-22: component-aware custom `Button`/`MacOSButton` sweep added with 142 historical findings.
- 2026-05-22: shared shell/mobile custom button labels cleanup removed 4 component findings.
- 2026-05-22: navigation/auth/prescription singleton labels cleanup removed 3 component findings.
- 2026-05-22: display content manager action labels cleanup removed 8 component findings.
- Current component-aware baseline: 127 findings.

## CI Policy

- `npm run audit:icon-controls:strict` fails when any icon-only control is added without a robust accessible name.
- `npm run audit:icon-controls:components` fails when any new project `Button`/`MacOSButton` icon-only control is added outside the current component baseline.
- The CI `frontend-lint` job runs the strict sweep after `npm run lint:check`.
- `npm run audit:icon-controls` remains available for baseline-aware local review, but the committed baseline is empty.

## Baseline Cleanup Completed

Completed cleanup order:

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
