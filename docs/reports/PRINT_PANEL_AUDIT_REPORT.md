# Print Panel Audit Report

Generated at: 2026-04-02
Mode: static code audit
Scope order: `registrar/cashier -> specialist panels -> laboratory -> admin`

## Summary

This audit maps the current print behavior across the clinic panels and classifies each user-facing scenario by implementation maturity:

- `A` - real backend/job/printer flow
- `B` - working PDF/download/open flow without real printer job delivery
- `C` - browser `window.print()` or local preview flow
- `D` - UI exists, but backend wiring is mocked, missing, or broken

Primary panel scenarios reviewed: **9**

- `A`: **1**
- `B`: **2**
- `C`: **4**
- `D`: **2**

Key conclusions:

- The codebase previously contained **multiple parallel print architectures** in backend and frontend, but the runtime now uses a single SSOT print API.
- The **registrar ticket dialog is a mock flow** and does not send a real print job.
- The **specialist panels mostly use `window.print()`**, not backend printer routing.
- **Dermatology prescription printing is broken** because `PrescriptionSystem` expects `onPrint`, but the panel does not pass it.
- The **lab workbench uses PDF export plus `markPrinted()`**, which is operationally useful but not a printer-job flow.
- The **admin cloud-printing panel is the closest thing to a real print control plane**, but real providers beyond `mock` depend on environment configuration.

## Acceptance Status

Audit acceptance criteria status for this pass:

- `[x]` Each target panel has a reviewed print scenario map
- `[x]` Each reviewed scenario is classified as `A/B/C/D`
- `[x]` Each finding has severity and remediation direction
- `[x]` Competing backend/frontend print entrypoints are inventoried
- `[x]` Legacy and non-primary print entrypoints are called out separately
- `[x]` Follow-up backlog is ordered for command-by-command execution

Notes:

- This pass is a **static implementation audit**. No new browser smoke or printer-device verification was run during this report generation step.
- No public APIs were changed as part of the audit.
- The scenario matrix below reflects the **audit snapshot**. Follow-up fixes removed the legacy frontend/backend print stack from runtime; see the retired stack section above for details.

## Architecture Inventory

### Active backend print contours

| Contour | Current role | Evidence |
|---|---|---|
| `backend/app/api/v1/endpoints/print_api.py` | Main structured print API for ticket, prescription, certificate, receipt, lab results, printers, quick flows | `print_api.py:34`, `:65`, `:111`, `:156`, `:185`, `:216`, `:302`, `:326` |
| `backend/app/services/print_service.py` | Backend printer service supporting `ESC/POS`, `A4`, `A5`, plus receipt and ticket generation | `print_service.py:98`, `:100`, `:317`, `:527`, `:626` |
| `backend/app/api/v1/endpoints/print.py` | Retired legacy PDF and ESC/POS endpoints; removed from runtime after SSOT consolidation | archived |
| `backend/app/api/v1/endpoints/print_templates.py` | Template CRUD, preview, formats, jobs metadata | `print_templates.py:35`, `:247`, `:349`, `:355`, `:397`, `:410` |
| `backend/app/api/v1/endpoints/cloud_printing.py` | Cloud-printing provider/job API including medical and quick print routes | `cloud_printing.py:257`, `:375`, `:419`, `:520` |
| `backend/app/services/cloud_printing_service.py` | Provider layer; adds `microsoft` only when env is present, always registers `mock` | `cloud_printing_service.py:421`, `:428`, `:429`, `:434` |
| `backend/app/api/v1/endpoints/payments.py` + `backend/app/services/payment_read_service.py` | Receipt metadata + receipt PDF download flow | `payments.py:288`, `:308`; `payment_read_service.py:270`, `:287`, `:305` |
| `backend/app/api/v1/endpoints/lab_reporting.py` | Lab PDF export and `mark-printed` state transition | `lab_reporting.py:496`, `:509`, `:518`, `:522` |

### Active frontend print entrypoints

| Entry point | Current role | Evidence |
|---|---|---|
| `frontend/src/components/dialogs/PrintDialog.jsx` | Registrar-facing dialog backed by the shared print service and backend printer inventory | `PrintDialog.jsx:68`, `:89`, `:120` |
| `frontend/src/pages/RegistrarPanel.jsx` | Opens registrar print dialog, but callback only logs | `RegistrarPanel.jsx:4202`, `:4208` |
| `frontend/src/components/PrescriptionSystem.jsx` | Specialist prescription UI that requires `onPrint` | `PrescriptionSystem.jsx:8`, `:93`, `:95`, `:386` |
| `frontend/src/components/laboratory/LabReportWorkbench.jsx` | Main lab print path via PDF download + `markPrinted()` | `LabReportWorkbench.jsx:443`, `:446` |
| `frontend/src/components/admin/CloudPrintingManager.jsx` | Admin UI for printers, statistics, test print, document print, medical print | `CloudPrintingManager.jsx:76`, `:107`, `:123`, `:142`, `:166` |
| `frontend/src/components/admin/ReportGenerator.jsx` | Admin reports browser print button | `ReportGenerator.jsx:541` |
| `frontend/src/services/print.js` | Canonical frontend print service facade for ticket, receipt, certificate, lab, and quick flows | `services/print.js:13`, `:49`, `:87`, `:132` |

### Retired legacy print stack

The following entrypoints were present during the audit but have since been removed from runtime:

- `backend/app/api/v1/endpoints/print.py`
- `frontend/src/components/PrintSystem.jsx`
- `frontend/src/components/print/PrintButton.jsx`
- `frontend/src/components/print/PrintDialog.jsx`

## Decision-Complete Scenario Matrix

| Panel | Scenario | Trigger | Current chain | Result type | Maturity | Severity |
|---|---|---|---|---|---|---|
| Registrar | Queue ticket print | Registrar row -> `PrintDialog` | UI dialog -> mock printers -> callback logs only | `mock` | `D` | `P0` |
| Cashier | Receipt print from history | Cashier row -> `handlePrintReceipt` | `CashierPanel` -> `usePayments.getReceipt()` -> cashier receipt endpoint/PDF metadata | `pdf` | `B` | `P1` |
| Cardiology | Queue/visit print | Panel row action | `window.print()` | `browser print` | `C` | `P1` |
| Dermatology | Queue/visit print | Panel row action | `window.print()` | `browser print` | `C` | `P1` |
| Dermatology | Prescription print | `PrescriptionSystem` print button | Button -> `await onPrint(...)` but no `onPrint` passed by panel | `broken` | `D` | `P0` |
| Dentistry | Queue/visit print | Panel row action | `window.print()` | `browser print` | `C` | `P1` |
| Laboratory | Results/report print | `LabReportWorkbench` print button | `downloadPdf()` -> open blob -> `markPrinted()` | `pdf` | `B` | `P1` |
| Admin | Cloud printing manager | Admin cloud-printing tools | Backend cloud-printing API -> provider layer -> real or mock provider | `printer job` | `A` | `P2` |
| Admin | Report generator print | Admin report print button | `window.print()` | `browser print` | `C` | `P2` |

## Detailed Audit Cards

### Registrar and Cashier

#### Card: Registrar queue ticket print

- Panel and screen: `RegistrarPanel`
- User goal: print queue ticket / appointment ticket from registrar workflow
- Trigger: row actions open the dialog and `RegistrarPanel` renders `<PrintDialog ... />`
- Evidence:
  - `frontend/src/pages/RegistrarPanel.jsx:2941`
  - `frontend/src/pages/RegistrarPanel.jsx:3654`
  - `frontend/src/pages/RegistrarPanel.jsx:3937`
  - `frontend/src/pages/RegistrarPanel.jsx:4202`
  - `frontend/src/pages/RegistrarPanel.jsx:4208`
  - `frontend/src/components/dialogs/PrintDialog.jsx:68`
  - `frontend/src/components/dialogs/PrintDialog.jsx:89`
  - `frontend/src/components/dialogs/PrintDialog.jsx:120`
- Current technical chain:
  - registrar opens the dialog
  - dialog loads `mockPrinters`
  - dialog simulates printing with timeout
  - callback returns to panel
  - panel logs `Printing:` but does not call backend print API
- Result type: `mock`
- Mandatory document data currently visible in UI:
  - patient
  - doctor
  - services
  - date/time
  - queue/ticket context
- What works:
  - user can open the dialog
  - UI exposes printer and document metadata
  - dialog closes with success feedback
- What does not work:
  - printer list is not backend-sourced
  - no print job is created
  - the success state is misleading because no real print happens
- Maturity: `D`
- Severity: `P0`
- Recommended fix:
  - replace dialog mock printer source with `/api/v1/print/printers`
  - send a real queue-ticket payload through a shared print facade
  - surface job success/failure from backend instead of simulated success
- Dependency type:
  - `Frontend`: dialog wiring
  - `Backend`: printer/source endpoint already exists
  - `Config`: printer registration
- Verification after fix:
  - open registrar ticket dialog
  - select real printer
  - confirm job creation on `/api/v1/print/ticket` or equivalent facade
  - validate backend response and operator feedback

#### Card: Cashier receipt print from history

- Panel and screen: `CashierPanel`
- User goal: print or retrieve payment receipt after successful payment
- Trigger: `handlePrintReceipt(paymentId)`
- Evidence:
  - `frontend/src/pages/CashierPanel.jsx:558`
  - `frontend/src/pages/CashierPanel.jsx:559`
  - `frontend/src/hooks/usePayments.js:367`
  - `frontend/src/hooks/usePayments.js:369`
  - `backend/app/api/v1/endpoints/payments.py:288`
  - `backend/app/api/v1/endpoints/payments.py:308`
  - `backend/app/services/payment_read_service.py:270`
  - `backend/app/services/payment_read_service.py:287`
  - `backend/app/services/payment_read_service.py:305`
- Current technical chain:
  - cashier requests receipt
  - frontend calls cashier receipt endpoint
  - backend returns receipt metadata including `receipt_url`
  - receipt download endpoint returns PDF
- Result type: `pdf`
- What works:
  - receipt generation path exists in backend
  - receipt PDF download endpoint exists
  - cashier UI is connected to a real backend path
- What does not work:
  - flow is not a printer-job flow
  - no explicit printer selection
  - no thermal-vs-regular printer routing in cashier panel
- Maturity: `B`
- Severity: `P1`
- Recommended fix:
  - keep PDF download as fallback/export path
  - add cashier-side direct print option via shared printer facade
  - support receipt template + target printer selection when needed
- Dependency type:
  - `Frontend`, `Transport`, `Printer source`
- Verification after fix:
  - cashier can either download PDF or send receipt to a configured printer
  - payment id and amount match the printed document

### Specialist Panels

#### Card: Cardiology queue/visit print

- Panel and screen: `CardiologistPanelUnified`
- User goal: print visit-related content from the cardiology panel
- Trigger: row action switch case
- Evidence:
  - `frontend/src/pages/CardiologistPanelUnified.jsx:920`
- Current technical chain:
  - panel calls `window.print()`
- Result type: `browser print`
- What works:
  - browser print dialog opens
- What does not work:
  - not routed through backend print templates
  - no printer-type selection
  - no structured clinical payload
- Maturity: `C`
- Severity: `P1`
- Recommended fix:
  - replace row-action browser print with document-type-specific backend print routing

#### Card: Dermatology queue/visit print

- Panel and screen: `DermatologistPanelUnified`
- User goal: print visit-related content from the dermatology panel
- Trigger: row action switch case
- Evidence:
  - `frontend/src/pages/DermatologistPanelUnified.jsx:643`
- Current technical chain:
  - panel calls `window.print()`
- Result type: `browser print`
- What works:
  - local browser print preview
- What does not work:
  - same weaknesses as cardiology
  - no structured doctor-document print contract
- Maturity: `C`
- Severity: `P1`
- Recommended fix:
  - migrate to shared clinical document print facade

#### Card: Dermatology prescription print

- Panel and screen: `DermatologistPanelUnified` + `PrescriptionSystem`
- User goal: print a saved prescription
- Trigger: prescription print button
- Evidence:
  - `frontend/src/components/PrescriptionSystem.jsx:8`
  - `frontend/src/components/PrescriptionSystem.jsx:93`
  - `frontend/src/components/PrescriptionSystem.jsx:95`
  - `frontend/src/components/PrescriptionSystem.jsx:386`
  - `frontend/src/pages/DermatologistPanelUnified.jsx:1549`
  - `frontend/src/pages/DermatologistPanelUnified.jsx:1781`
- Current technical chain:
  - `PrescriptionSystem` calls `await onPrint(prescription)`
  - the dermatology panel mounts `PrescriptionSystem`
  - the panel does not pass `onPrint`
- Result type: `broken`
- What works:
  - prescription UI and save path exist
  - print control is visible
- What does not work:
  - print callback contract is incomplete
  - clicking print can fail at runtime
  - no prescription printer routing is connected despite backend support existing in `print_api.py`
- Maturity: `D`
- Severity: `P0`
- Recommended fix:
  - pass a real `onPrint` handler from the panel
  - route saved prescription data to `/api/v1/print/prescription` or the shared print facade
  - disable the button when a valid print handler is not available
- Dependency type:
  - `Wiring`, `Data contract`
- Verification after fix:
  - save prescription
  - press print
  - observe backend request and correct document content

#### Card: Dentistry queue/visit print

- Panel and screen: `DentistPanelUnified`
- User goal: print visit-related content from the dentistry panel
- Trigger: row action switch case
- Evidence:
  - `frontend/src/pages/DentistPanelUnified.jsx:773`
- Current technical chain:
  - panel calls `window.print()`
- Result type: `browser print`
- What works:
  - browser print preview
- What does not work:
  - no document type abstraction
  - no printer selection
  - no link to receipt/prescription/report templates
- Maturity: `C`
- Severity: `P1`
- Recommended fix:
  - migrate dentistry print actions to the same shared facade as cardiology and dermatology

### Laboratory

#### Card: Lab report/result print

- Panel and screen: `LabPanel` -> `LabReportWorkbench`
- User goal: print finalized lab results and support reprint behavior
- Trigger: workbench print action
- Evidence:
  - `frontend/src/pages/LabPanel.jsx:452`
  - `frontend/src/components/laboratory/LabReportWorkbench.jsx:443`
  - `frontend/src/components/laboratory/LabReportWorkbench.jsx:446`
  - `backend/app/api/v1/endpoints/lab_reporting.py:496`
  - `backend/app/api/v1/endpoints/lab_reporting.py:509`
  - `backend/app/api/v1/endpoints/lab_reporting.py:518`
  - `backend/app/api/v1/endpoints/lab_reporting.py:522`
- Current technical chain:
  - only `FINALIZED` / `PRINTED` reports can export PDF
  - frontend downloads PDF blob
  - frontend opens the PDF in a new tab
  - frontend marks the report as printed
- Result type: `pdf`
- What works:
  - finalized-state guard exists
  - PDF export exists
  - `PRINTED` status transition exists
- What does not work:
  - this is not a real printer job
  - no printer target selection
  - no distinction between thermal and standard printers
- Reprint behavior:
  - the code path preserves report-state semantics better than browser print because `markPrinted()` is explicit
  - however, it still treats PDF export as the final delivery mechanism
- Maturity: `B`
- Severity: `P1`
- Recommended fix:
  - decide whether PDF export is the accepted target mode for lab
  - if not, add backend printer delivery on top of the existing PDF generation path
  - preserve `PRINTED` semantics for both first print and reprint

### Admin

#### Card: Cloud printing manager

- Panel and screen: `AdminPanel` -> `CloudPrintingManager`
- User goal: manage printers, send test print, send document print, send medical print, view statistics
- Trigger: admin cloud-printing section
- Evidence:
  - `frontend/src/pages/AdminPanel.jsx:160`
  - `frontend/src/pages/AdminPanel.jsx:1154`
  - `frontend/src/pages/AdminPanel.jsx:2550`
  - `frontend/src/components/admin/CloudPrintingManager.jsx:76`
  - `frontend/src/components/admin/CloudPrintingManager.jsx:107`
  - `frontend/src/components/admin/CloudPrintingManager.jsx:123`
  - `frontend/src/components/admin/CloudPrintingManager.jsx:142`
  - `frontend/src/components/admin/CloudPrintingManager.jsx:166`
  - `backend/app/api/v1/endpoints/cloud_printing.py:257`
  - `backend/app/api/v1/endpoints/cloud_printing.py:375`
  - `backend/app/api/v1/endpoints/cloud_printing.py:419`
  - `backend/app/api/v1/endpoints/cloud_printing.py:520`
  - `backend/app/services/cloud_printing_service.py:421`
  - `backend/app/services/cloud_printing_service.py:428`
  - `backend/app/services/cloud_printing_service.py:429`
  - `backend/app/services/cloud_printing_service.py:434`
- Current technical chain:
  - admin UI calls real cloud-printing backend endpoints
  - backend provider layer can route to `microsoft`
  - if Microsoft credentials are absent, service still exposes `mock`
  - frontend also falls back to demo data if API calls fail
- Result type: `printer job`
- What works:
  - this is the strongest end-to-end print integration in the codebase
  - statistics, test print, generic print, and medical print routes exist
- What does not work:
  - production value depends on environment configuration
  - mock provider is always present
  - frontend fallback-to-demo can mask missing real integration
- Maturity: `A`
- Severity: `P2`
- Recommended fix:
  - keep this contour as the admin/operator control plane
  - expose provider health more explicitly
  - distinguish "real provider online" from "demo/mock" in the UI
- Dependency type:
  - `Config`, `Printer source`, `Role/access`

#### Card: Admin report generator print

- Panel and screen: admin report generation UI
- User goal: print generated reports
- Trigger: report print button
- Evidence:
  - `frontend/src/components/admin/ReportGenerator.jsx:541`
- Current technical chain:
  - report UI calls `window.print()`
- Result type: `browser print`
- What works:
  - browser print preview
- What does not work:
  - no shared print routing
  - no job tracking
  - no printer selection
- Maturity: `C`
- Severity: `P2`
- Recommended fix:
  - decide whether admin reports should remain browser/PDF oriented or join the shared printer facade

## Legacy Drift and Secondary Entry Points

These do not appear to be the main current panel flows, but they matter because they split the print architecture and can mislead future fixes.

### Unused or drifted print components

| Component | Current state | Evidence | Risk |
|---|---|---|---|
| `frontend/src/components/print/PrintButton.jsx` | Backend-aware print facade appears unused | `PrintButton.jsx:59-63`; repo search returned no current usages | Good idea, but not connected to live panels |
| `frontend/src/components/print/PrintDialog.jsx` | Backend-aware dialog appears unused and calls a preview route that does not match backend | `components/print/PrintDialog.jsx:40`, `:75`; backend `print_templates.py:247` requires `/templates/{template_id}/preview` | Preview contract mismatch |
| `frontend/src/components/PrintSystem.jsx` | Appears unused and calls `/api/v1/print/test`, which is not the current backend route shape | `PrintSystem.jsx:22`; backend test route is `print_api.py:273` under `/printers/{printer_name}/test` | Dead or misleading integration path |
| `frontend/src/services/print.js` | Appears unused; `quickPrint()` posts to `/print/quick`, while backend quick routes are `/print/quick/queue-ticket` and `/print/quick/payment-receipt` | `services/print.js:87`; backend `print_api.py:302`, `:326` | Facade drift vs backend SSOT |

### Secondary browser-print paths

These should be treated as legacy or panel-adjacent until explicitly promoted into supported workflows:

- `frontend/src/components/dental/TreatmentPlanner.jsx:132`
- `frontend/src/components/laboratory/LabReportGenerator.jsx:173`
- `frontend/src/components/payment/PaymentClick.jsx:284`
- `frontend/src/components/payment/PaymentPayMe.jsx:284`
- `frontend/src/components/queue/OnlineQueueManager.jsx:563`
- `frontend/src/components/tickets/MultipleTicketsPrinter.jsx:65`
- `frontend/src/pages/PatientPickupView.jsx:131`
- `frontend/src/pages/PaymentSuccess.jsx:139`

### Payment-success supplementary path

`PaymentSuccess.jsx` is not the main cashier panel, but it is a real payment-adjacent print path:

- `frontend/src/pages/PaymentSuccess.jsx:41`
- `frontend/src/pages/PaymentSuccess.jsx:46`
- `frontend/src/pages/PaymentSuccess.jsx:87`
- `frontend/src/pages/PaymentSuccess.jsx:139`
- `frontend/src/services/payment.js:70`
- `frontend/src/services/payment.js:89`
- `frontend/src/services/payment.js:91`

Behavior:

- can open `receipt_url` in a new tab
- also has a browser-print fallback via `printWindow.print()`

Classification:

- `B/C` mixed supplementary flow

## Gap Analysis by Category

### Wiring

- Registrar print dialog does not call backend.
- Dermatology prescription print button has no connected `onPrint`.
- Several specialist panels wire print directly to `window.print()` instead of a shared print facade.

### Data contract

- Specialist print actions do not declare a stable `documentType + payload + printer target` contract.
- Registrar and specialist flows do not consistently pass visit/payment identifiers into a unified print service.

### Printer source

- Registrar uses hardcoded printer inventory.
- Admin cloud printing can fall back to demo data even when the API path is unhealthy.

### Template/render

- Specialist browser print flows bypass backend templates entirely.
- Unused `components/print/PrintDialog.jsx` points to a preview route that does not match backend template preview.

### Transport

- Cashier and lab rely on PDF/open-tab delivery rather than printer-job delivery.
- Multiple legacy components print through browser windows or injected HTML.

### Role/access

- Cloud printing is the only clear role-scoped print control plane.
- Other panels have not been normalized onto a role-aware print API surface.

### Legacy drift

- The codebase currently contains at least four competing print strategies:
  - mock dialog print
  - backend print API
  - PDF/open/download print
  - browser `window.print()`

## Prioritized Backlog

### Priority 1: Broken prescriptions and clinical documents

1. Fix dermatology prescription printing by passing a real `onPrint` handler.
2. Define a shared specialist print facade for prescription, recommendation, and visit documents.
3. Replace panel-level `window.print()` usage in cardiology, dermatology, and dentistry for supported clinical documents.

### Priority 2: Cashier receipts and registrar tickets

1. Replace registrar mock printers with backend printer inventory.
2. Wire registrar ticket print to the real ticket print endpoint/facade.
3. Add direct-printer cashier receipt support while keeping PDF download as fallback/export.

### Priority 3: Lab results and reprint flow

1. Decide whether lab PDF export is the accepted final mode.
2. If not, add real printer-job delivery while preserving `PRINTED` state semantics.
3. Normalize reprint behavior around explicit backend job creation.

### Priority 4: Admin and analytics reports

1. Decide whether admin reports stay browser/PDF oriented or move to printer-job flow.
2. Make cloud-printing UI explicitly show real-provider vs mock/demo state.

### Priority 5: Unification and cleanup

1. Pick a single frontend print facade.
2. Retire or rewrite unused drifted components:
   - `components/print/PrintButton.jsx`
   - `components/print/PrintDialog.jsx`
   - `components/PrintSystem.jsx`
   - `services/print.js`
3. Align preview and quick-print contracts to the real backend routes.

## Target-State Contract

The audit supports the following default target contract for future fixes:

- Panels should not call `window.print()` for clinical or operational documents when a backend print flow exists.
- A shared frontend print facade should own:
  - `documentType`
  - `payload`
  - `printer target`
  - `transport mode`
  - `job feedback`
- Printer inventory must come from backend source of truth.
- Prescription, recommendation, receipt, ticket, and lab report flows should explicitly distinguish:
  - thermal / `ESC/POS`
  - standard / `A4`
  - standard / `A5`
- PDF export may remain as a fallback/export mode, but should not masquerade as a printer-job flow.

## Recommended Next Execution Order

When you start issuing fix commands, the safest sequence is:

1. `Dermatology prescription print wiring`
2. `Registrar ticket print real backend flow`
3. `Shared specialist print facade`
4. `Cashier receipt direct-printer option`
5. `Lab print transport decision and implementation`
6. `Legacy print cleanup and route-contract normalization` [completed]
