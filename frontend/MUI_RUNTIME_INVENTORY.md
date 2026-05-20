# MUI Runtime Inventory

Date: 2026-05-20

Scope: `frontend/src/pages` and `frontend/src/components`

Command used:

```powershell
rg -l "@mui|Mui" frontend\src\pages frontend\src\components
rg -n "@mui|Mui" frontend\src\pages frontend\src\components
```

Initial count: 16 files with runtime or example MUI imports.

Current count after PR-UX-9 inventory refresh: 14 files with runtime or example MUI imports.

PR-UX-17 decision refresh: 14 files still contain runtime or example MUI imports.
The two previous low-risk PWA runtime islands remain migrated. No additional
low-risk runtime island is safe to migrate in this cycle without crossing into
admin user management, queue, payment, lab reporting, patient clinical data,
cardiology, dental, Telegram, AI/MCP, or example-only policy work.

PR-MUI-1 decision refresh after the performance split cycle: 14 files still
contain runtime or example MUI imports. PR-PERF-9 through PR-PERF-12 did not add
new MUI islands. The remaining classification is unchanged: every runtime target
is shared/admin-sensitive, payment/queue-adjacent, clinical-heavy, or
Telegram/AI-sensitive; the two `components/examples` files remain example-only
until the example policy is decided.

## No-New-MUI Island Policy

MUI is a legacy compatibility layer in this clinic frontend. New clinic runtime UI should not create new MUI islands.

Default rule:

- Do not add new `@mui/material`, `@mui/icons-material`, `@mui/system`, or `@material-ui/*` imports in app pages, route panels, workflow components, forms, tables, dashboards, empty/loading/error states, payment flows, queue flows, EMR/lab/dental/cardiology surfaces, Telegram management, or authenticated role UI.
- Use `frontend/src/components/ui/macos` and the macOS token/CSS variable layer first.
- If a touched file already imports MUI, do not expand its MUI surface. Leave the existing island in place unless the PR is explicitly a scoped MUI migration.
- A new MUI import requires explicit approval in the PR body with:
  - the exact file and UI surface;
  - why the canonical macOS primitive cannot safely cover the need;
  - the intended follow-up or migration/retirement path;
  - validation that no route, RBAC, payment, queue, EMR, lab, Telegram, notification, or backend contract changed.
- MUI removal must be staged one file or one component family at a time. Do not mass-remove MUI dependencies until runtime imports reach `0`.

Review command for future PRs:

```powershell
rg -l '@mui|Mui' frontend/src/pages frontend/src/components
```

## Policy

- Canonical app UI layer remains `frontend/src/components/ui/macos` per `frontend/DESIGN_SYSTEM.md`.
- Do not add new MUI usage in clinic app pages or workflow panels.
- Do not remove MUI dependencies until runtime imports reach `0`.
- Migrate only one low-risk runtime file per slice unless a later gate or handoff explicitly approves broader work.
- Leave dental, cardiology, lab, queue, payment, Telegram, AI, and EMR-adjacent files untouched until a dedicated gate/handoff reviews domain behavior.

## Inventory

| File | Risk class | Notes | Migration decision |
| --- | --- | --- | --- |
| `frontend/src/components/pwa/ConnectionStatus.jsx` | Low-risk | PWA online/offline/sync status UI; no backend contract ownership. | Migrated in Task 36; no current `@mui` import. |
| `frontend/src/components/pwa/PWAInstallPrompt.jsx` | Low-risk | PWA install/update/notification prompt UI. | Migrated in Task 37; no current `@mui` import. |
| `frontend/src/components/admin/UserManagement.jsx` | Shared/admin-sensitive | Legacy actions menu imports MUI. Admin user workflow is role-sensitive. | Do not touch until dedicated admin slice. |
| `frontend/src/components/dashboard/Dashboard.jsx` | Shared/admin-sensitive | Dashboard summary UI with MUI icons/components. | Leave for later dashboard consolidation. |
| `frontend/src/components/payment/PaymentWidget.jsx` | Payment/queue-adjacent | Payment flow behavior and error handling are payment-sensitive. | Gate/handoff only. |
| `frontend/src/pages/PaymentTest.jsx` | Payment/queue-adjacent | Internal payment demo/test surface. | Gate/handoff only; do not alter payment semantics. |
| `frontend/src/components/queue/OnlineQueueManager.jsx` | Payment/queue-adjacent | Queue status, print/download, and queue operations. | Gate/handoff only. |
| `frontend/src/components/patient/FamilyRelationsCard.jsx` | Clinical-heavy | Patient relationship data and visibility semantics. | Clinical safety review before migration. |
| `frontend/src/components/laboratory/LabReportGenerator.jsx` | Clinical-heavy | Lab report generation UI. | Clinical safety review before migration. |
| `frontend/src/components/cardiology/ECGViewer.jsx` | Clinical-heavy | ECG viewer and cardiology data display. | Clinical safety review before migration. |
| `frontend/src/components/dental/TreatmentPlanner.jsx` | Clinical-heavy | Dental treatment planning and cost/status semantics. | Clinical safety review before migration. |
| `frontend/src/components/dental/ToothModal.jsx` | Clinical-heavy | Dental tooth modal and clinical status semantics. | Clinical safety review before migration. |
| `frontend/src/components/TelegramManager.jsx` | Telegram/AI-sensitive | Telegram integration management. | Gate/handoff only. |
| `frontend/src/components/ai/MCPMonitor.jsx` | Telegram/AI-sensitive | AI/MCP monitoring surface. | Gate/handoff only; preserve AI safety copy. |
| `frontend/src/components/examples/UnifiedCard.tsx` | Example-only | Design-system example file. | Do not count as blocking app runtime until examples policy is decided. |
| `frontend/src/components/examples/UnifiedButton.tsx` | Example-only | Design-system example file. | Do not count as blocking app runtime until examples policy is decided. |

## Do-Not-Touch Buckets

- Dental: `TreatmentPlanner.jsx`, `ToothModal.jsx`
- Cardiology: `ECGViewer.jsx`
- Lab: `LabReportGenerator.jsx`
- Queue: `OnlineQueueManager.jsx`
- Payment: `PaymentWidget.jsx`, `PaymentTest.jsx`
- Telegram: `TelegramManager.jsx`
- AI: `MCPMonitor.jsx`
- Patient clinical data: `FamilyRelationsCard.jsx`

## Completed Low-Risk Runtime Targets

1. `frontend/src/components/pwa/ConnectionStatus.jsx`
2. `frontend/src/components/pwa/PWAInstallPrompt.jsx`

These targets were low-risk because they are UI-status prompts and were migrated without changing PWA hooks, online/offline behavior, service worker sync handling, notification permission logic, or install/update gating.

## Remaining Runtime Targets

The remaining current `@mui` files are all in do-not-touch buckets or shared/admin-sensitive/example-only categories. Do not migrate them without a dedicated gate/handoff.

## PR-UX-17 Decision

PR-UX-17 is intentionally documentation-only.

Fresh command:

```powershell
$files = rg -l '@mui|Mui' frontend/src/pages frontend/src/components
$files | Sort-Object
$files.Count
```

Result: 14 files.

Decision: do not force a runtime MUI migration in this PR. The only already
approved low-risk runtime targets were `ConnectionStatus.jsx` and
`PWAInstallPrompt.jsx`, and both are already migrated. Every remaining runtime
target has a domain or workflow risk that should be handled as its own bounded
handoff:

- Admin/user management: preserve RBAC, account actions, and legacy action menu behavior.
- Dashboard: plan a dashboard consolidation slice before changing summary cards or menus.
- Queue/payment: protect queue status, payment state, receipts, and print/download actions.
- Lab/cardiology/dental/patient: preserve clinical meaning, report generation, ECG/dental status, and patient relationship visibility.
- Telegram/AI/MCP: preserve integration status, security copy, and operational diagnostics.
- Examples: decide whether example-only files stay as MUI design-system references before counting them as runtime cleanup.

Next safe MUI migration should be a dedicated PR with one first-touch file,
route/browser smoke, and a PR body that explicitly proves no role, route,
payment, queue, EMR, lab, Telegram, notification, or backend contract changed.

## PR-MUI-1 Refresh

PR-MUI-1 is intentionally inventory-only after the AdminPanel performance split
cycle.

Fresh command:

```powershell
rg -l "@mui|Mui" frontend\src\pages frontend\src\components
rg -n "@mui|Mui" frontend\src\pages frontend\src\components
```

Result: 14 files.

No new MUI imports were introduced by the recent performance PRs. Current
classification:

| Category | Files | Decision |
| --- | ---: | --- |
| Shared/admin-sensitive | 2 | Requires dedicated admin/dashboard slice. |
| Payment/queue-adjacent | 3 | Gate/handoff only. |
| Clinical-heavy | 5 | Clinical safety review before migration. |
| Telegram/AI-sensitive | 2 | Gate/handoff only. |
| Example-only | 2 | Decide example policy before counting as runtime cleanup. |

Current files:

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

Decision: do not migrate MUI in PR-MUI-1. The next safe step is PR-MUI-2 only
if one low-risk admin island can be scoped with browser proof; otherwise move to
PR-MUI-3 example-only policy.
