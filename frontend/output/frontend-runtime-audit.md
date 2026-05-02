# Frontend Runtime File Audit

Date: 2026-03-05  
Scope: `frontend/src`

## Method

1. Build runtime dependency graph from app entrypoint:
   - `npx madge --extensions js,jsx --json frontend/src/main.jsx`
2. Compare graph (reachable files) with all source files:
   - `**/*.{js,jsx,ts,tsx,css,json}`
3. Split unreachable files into categories:
   - `tests`, `stories`, `scripts`, `legacy_or_demo`, `runtime_orphans`

## Results

- Total scanned files: `716`
- Reachable from runtime entry (`main.jsx`): `493`
- Unreachable candidates: `223`

Breakdown:

- `tests`: `25`
- `stories`: `3`
- `scripts`: `3`
- `legacy_or_demo`: `14`
- `runtime_orphans`: `178`

Full categorized list: [frontend-unused-categories.json](/c:/final/frontend/output/frontend-unused-categories.json)

## Active Runtime Pages

The following page modules are currently reachable from runtime routing:

- `pages/AdminPanel.jsx`
- `pages/AnalyticsPage.jsx`
- `pages/Appointments.jsx`
- `pages/Audit.jsx`
- `pages/CSSTestPage.jsx`
- `pages/CardiologistPanelUnified.jsx`
- `pages/CashierPanel.jsx`
- `pages/DentistPanelUnified.jsx`
- `pages/DermatologistPanelUnified.jsx`
- `pages/DisplayBoardUnified.jsx`
- `pages/DoctorPanel.jsx`
- `pages/EMRDemo.jsx`
- `pages/EMRv2Demo.jsx`
- `pages/Health.jsx`
- `pages/LabPanel.jsx`
- `pages/Landing.jsx`
- `pages/Login.jsx`
- `pages/MacOSDemoPage.jsx`
- `pages/MediLabDemo.jsx`
- `pages/PatientPanel.jsx`
- `pages/PatientPickupView.jsx`
- `pages/PaymentCancel.jsx`
- `pages/PaymentSuccess.jsx`
- `pages/PaymentTest.jsx`
- `pages/QueueJoin.jsx`
- `pages/RegistrarPanel.jsx`
- `pages/Scheduler.jsx`
- `pages/Search.jsx`
- `pages/SecurityPage.jsx`
- `pages/Settings.jsx`
- `pages/SingleSheetEMRDemo.jsx`
- `pages/UserProfile.jsx`
- `pages/UserSelect.jsx`
- `pages/VisitDetails.jsx`
- `pages/auth/ChangePasswordRequired.jsx`

## High-Confidence Legacy/Duplicate Files

These are unreachable and have direct active replacements or explicit legacy markers:

- `components/wizard/AppointmentWizard.OLD.jsx`
- `components/ai/TreatmentRecommendations_backup.jsx`
- `pages/NewApp.jsx`
- `theme/ThemeProvider.jsx`
- `theme/ThemeProvider.tsx`
- `theme/ThemeProviderSetup.tsx`
- `components/print/PrintDialog.jsx` (active replacement: `components/dialogs/PrintDialog.jsx`)
- `components/mobile/PWAInstallPrompt.jsx` (active replacement: `components/pwa/PWAInstallPrompt.jsx`)
- `components/PWAInstallPrompt.jsx` (active replacement: `components/pwa/PWAInstallPrompt.jsx`)
- `components/telegram/TelegramManager.jsx` (active replacement: `components/TelegramManager.jsx`)
- `components/layout/Sidebar.jsx` (active replacement: `components/ui/macos/Sidebar.jsx`)
- `components/AnimatedTransition.jsx` (active replacement: `components/ui/native/AnimatedTransition.jsx`)

## Working Rule For Ongoing Tasks

Continue implementation only in files that are reachable from runtime graph.  
Treat files from `frontend-unused-categories.json` as non-active unless explicitly reconnected to routing/import graph.
