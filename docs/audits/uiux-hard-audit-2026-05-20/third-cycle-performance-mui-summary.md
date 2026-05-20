# Third UI/UX Performance And MUI Debt Cycle Summary

Date: 2026-05-20

## Scope

This summary closes the third UI/UX performance and MUI debt cycle. It is
documentation-only and does not change runtime frontend/backend behavior.

## Merged PRs

| Slice | PR | Result |
| --- | ---: | --- |
| PR-3-0: third-cycle checklist | #954 | Merged |
| PR-PERF-9: Vite warning baseline refresh | #958 | Merged |
| PR-PERF-10: lazy-load admin reports view | #960 | Merged |
| PR-PERF-11: lazy-load wait time analytics view | #962 | Merged |
| PR-PERF-12: post-split AdminPanel review | #963 | Merged |
| PR-MUI-1: MUI inventory refresh | #965 | Merged |
| PR-MUI-2: admin MUI migration decision | #966 | Merged |
| PR-MUI-3: example-only MUI policy | #967 | Merged |
| PR-MUI-4: risky MUI islands handoff | #968 | Merged |

All PRs were opened as small branches from fresh `origin/main`, passed GitHub
checks, and were merged before the next cycle step continued.

## Performance Result

The cycle kept the Vite warning signal honest:

- `chunkSizeWarningLimit` was not increased.
- The initial `index-*` chunk stayed below the configured warning threshold in
  the documented build evidence.
- `heic2any-*` remains isolated as a lazy conversion dependency.
- `AdminPanel-*` dropped below the local `1000 KiB` review target after the
  reports and wait-time analytics lazy boundaries.

Current documented local build evidence after PR-PERF-12:

| Asset | Approx size |
| --- | ---: |
| `index-*` | `1400.99 KiB` |
| `heic2any-*` | `1320.46 KiB` |
| `AdminPanel-*` | `970.11 KiB` |
| `AnalyticsPage-*` | `245.86 KiB` |
| `RegistrarPanel-*` | `245.68 KiB` |
| `DentistPanelUnified-*` | `243.58 KiB` |
| `ServiceCatalog-*` | `46.51 KiB` |
| `UnifiedReports-*` | `35.25 KiB` |
| `WaitTimeAnalytics-*` | `19.27 KiB` |

## Historical MUI Status

Fresh inventory command:

```powershell
rg -l "@mui|Mui" frontend\src\pages frontend\src\components
```

Historical count at third-cycle close: 14 files.

Historical classification:

- Shared/admin-sensitive:
  - `frontend/src/components/admin/UserManagement.jsx`
  - `frontend/src/components/dashboard/Dashboard.jsx`
- Payment/queue-adjacent:
  - `frontend/src/components/payment/PaymentWidget.jsx`
  - `frontend/src/pages/PaymentTest.jsx`
  - `frontend/src/components/queue/OnlineQueueManager.jsx`
- Clinical-heavy:
  - `frontend/src/components/patient/FamilyRelationsCard.jsx`
  - `frontend/src/components/laboratory/LabReportGenerator.jsx`
  - `frontend/src/components/cardiology/ECGViewer.jsx`
  - `frontend/src/components/dental/TreatmentPlanner.jsx`
  - `frontend/src/components/dental/ToothModal.jsx`
- Telegram/AI-sensitive:
  - `frontend/src/components/TelegramManager.jsx`
  - `frontend/src/components/ai/MCPMonitor.jsx`
- Example-only:
  - `frontend/src/components/examples/UnifiedButton.tsx`
  - `frontend/src/components/examples/UnifiedCard.tsx`

The cycle intentionally did not force a runtime MUI migration after the two
previous low-risk PWA targets had already been migrated. The remaining runtime
targets now require dedicated guarded handoffs.

## Completed Decisions

- No low-risk admin MUI island currently satisfies both first-touch and
  route/browser proof requirements.
- `UnifiedButton.tsx` and `UnifiedCard.tsx` are example-only MUI debt, not
  active clinic runtime UI.
- Payment, queue, clinical, Telegram/AI, and admin/shared MUI islands must be
  migrated only through one-island gated PRs with browser/auth proof.

## Remaining Backlog

Recommended next slices:

1. Dashboard route-owner discovery:
   confirm whether `frontend/src/components/dashboard/Dashboard.jsx` is unused,
   indirectly mounted, or safe to archive.
2. Admin user actions menu migration:
   dedicated `UserManagement.jsx` slice with authenticated admin browser proof
   and destructive-action keyboard/focus validation.
3. Payment MUI handoff execution:
   one payment file only, preserving request/response/status/receipt semantics.
4. Queue MUI handoff execution:
   one queue file only, preserving queue ordering, status, and print/download
   behavior.
5. Clinical MUI handoff execution:
   one specialty or patient file per PR after role-authenticated browser proof.
6. Example cleanup:
   convert `UnifiedButton.tsx` and `UnifiedCard.tsx` to macOS examples, archive
   them, or delete them after confirming no developer workflow still uses them.

## Validation Trail

Docs/policy PRs used:

- `git diff --check`
- PR review body template gate
- static MUI inventory/caller searches
- GitHub Actions required checks before merge

Runtime performance PRs used:

- route ownership test where applicable
- frontend lint
- frontend build
- asset inventory review
- GitHub Actions required checks before merge

## Current Completion State

The third cycle is complete. Remaining MUI debt is no longer ambiguous: it is
classified, policy-covered, and guarded for future small PRs.

## Post-Cycle Continuation Note

Later small PRs reduced the current MUI inventory from the historical third
cycle count of 14 files to 0 files:

- stale `frontend/src/components/dashboard/Dashboard.jsx` removal;
- gated `frontend/src/components/admin/UserManagement.jsx` actions menu
  migration;
- `frontend/src/components/examples/UnifiedButton.tsx` and
  `frontend/src/components/examples/UnifiedCard.tsx` conversion to
  macOS/native examples;
- gated `frontend/src/pages/PaymentTest.jsx` internal demo migration.
- stale caller-free `frontend/src/components/ai/MCPMonitor.jsx` removal.
- stale caller-free `frontend/src/components/laboratory/LabReportGenerator.jsx`
  removal.
- gated `frontend/src/components/patient/FamilyRelationsCard.jsx` patient
  relationship migration.
- gated `frontend/src/components/dental/TreatmentPlanner.jsx` dental treatment
  planning migration.
- gated `frontend/src/components/dental/ToothModal.jsx` dental tooth modal
  migration.
- gated `frontend/src/components/payment/PaymentWidget.jsx` payment widget
  migration.
- gated `frontend/src/components/cardiology/ECGViewer.jsx` cardiology viewer
  migration.
- gated `frontend/src/components/queue/OnlineQueueManager.jsx` queue manager
  migration.
- gated `frontend/src/components/TelegramManager.jsx` Telegram integration
  migration.

Current remaining MUI files:

- none currently matching `@mui|Mui` in `frontend/src/pages` or
  `frontend/src/components`.

Next smallest MUI-related step is a separate dependency/package audit before
removing any `@mui/*` packages.
