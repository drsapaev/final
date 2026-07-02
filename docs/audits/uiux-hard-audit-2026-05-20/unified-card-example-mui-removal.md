# UnifiedCard Example MUI Removal

Date: 2026-05-20

## Scope

Converted the example-only card reference:

- `frontend/src/components/examples/UnifiedCard.tsx`

This PR did not touch runtime clinic routes, role panels, backend code, RBAC,
payment, queue, clinical workflows, Telegram, AI/MCP, or notification behavior.

## Why This Was Safe

`UnifiedCard.tsx` was classified as example-only debt in
`frontend/MUI_RUNTIME_INVENTORY.md` and
`docs/audits/uiux-hard-audit-2026-05-20/mui-example-only-policy.md`.

Static search found documentation references, but no active app route importing
or rendering `UnifiedCard`:

```powershell
rg -n "UnifiedCard|UnifiedButton|MacOSDemo|components/examples" frontend\src\routing frontend\src\pages frontend\src\components -g "!*UnifiedCard.tsx"
```

Observed route evidence:

- `frontend/src/pages/MacOSDemoPage.jsx` lazy-loads `components/examples/MacOSDemo`.
- `UnifiedCard.tsx` is not imported by active app pages or route registry files.

## Changed

- Removed all `@mui/material` imports from `UnifiedCard.tsx`.
- Removed MUI `styled` and MUI `useTheme`.
- Preserved the public example exports:
  - `UnifiedCard`
  - `UnifiedCardShowcase`
- Preserved the example props and variants:
  - `variant`
  - `title`
  - `subtitle`
  - `children`
  - `actions`
  - `onClick`
  - `interactive`
  - `size`
- Added keyboard semantics for interactive cards with `role="button"`,
  `tabIndex=0`, and Enter/Space handling.
- Replaced MUI showcase actions with native buttons styled by existing macOS
  CSS variables.

## MUI Count

After this slice:

```powershell
rg -l '@mui|Mui' frontend\src\pages frontend\src\components
```

Result: 10 files.

The remaining files are all runtime domain islands:

- Payment/queue: `PaymentWidget.jsx`, `PaymentTest.jsx`,
  `OnlineQueueManager.jsx`
- Clinical: `FamilyRelationsCard.jsx`, `LabReportGenerator.jsx`,
  `ECGViewer.jsx`, `TreatmentPlanner.jsx`, `ToothModal.jsx`
- Telegram/AI: `TelegramManager.jsx`, `MCPMonitor.jsx`

## Validation Plan

- Route ownership test for route registry regressions.
- Frontend lint.
- Frontend build.
- Static MUI count.
- `git diff --check`.

## Stop Conditions

Stop if:

- `UnifiedCard.tsx` is found to be an active runtime route dependency.
- Preserving its example API requires touching app pages or route registry files.
- The change requires payment, queue, clinical, Telegram, AI/MCP, RBAC, backend,
  or notification behavior changes.

## Next Smallest Step

Move to the risky runtime MUI backlog only through dedicated gate/handoff slices.
Do not combine payment, queue, clinical, Telegram, or AI/MCP MUI migrations in a
generic cleanup PR.
