# MUI Runtime Inventory

Date: 2026-05-15

Scope: `frontend/src/pages` and `frontend/src/components`

Command used:

```powershell
rg -l "@mui|Mui" frontend\src\pages frontend\src\components
rg -n "@mui|Mui" frontend\src\pages frontend\src\components
```

Initial count: 16 files with runtime or example MUI imports.

Current count after Tasks 36-37: 14 files with runtime or example MUI imports.

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
