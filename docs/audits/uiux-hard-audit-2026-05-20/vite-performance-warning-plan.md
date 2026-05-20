# Vite Performance Warning Plan

Date: 2026-05-20

Scope: report-only baseline for PR-PERF-1. No runtime code, Vite config,
imports, routes, tests, backend, or deployment behavior changed in this PR.

## Baseline Command

```powershell
cd frontend
npm.cmd run build
```

Result: build passed.

Observed build stats:

- Vite `6.4.2`
- Modules transformed: `14002`
- Build time: `26.89s`
- Current `chunkSizeWarningLimit`: `1500` KB in `frontend/vite.config.js`

## Current Warnings

### P1 - Oversized JavaScript Chunks

Vite still reports chunks larger than `1500` KB after minification.

Largest generated JavaScript assets from the current build:

| Asset | Size |
| --- | ---: |
| `index-BYQkHiui.js` | `1732.33 KB` |
| `heic2any-BJtmzsQg.js` | `1320.09 KB` |
| `AdminPanel-Om2b9RoN.js` | `1100.97 KB` |
| `DentistPanelUnified-BdCG30Nh.js` | `256.14 KB` |
| `AnalyticsPage-CRKh4Q3d.js` | `245.76 KB` |
| `RegistrarPanel-BVrHlnDn.js` | `245.60 KB` |
| `canonicalVisit-Bv9z6DaW.js` | `166.47 KB` |
| `DermatologistPanelUnified-CcdNCNA5.js` | `125.40 KB` |
| `panelPrint-Bx3kfTfb.js` | `107.93 KB` |
| `LabPanel-BT6YIe2K.js` | `59.70 KB` |
| `index-Bw5o297R.js` | `58.60 KB` |
| `CashierPanel-g-KW4sHu.js` | `49.91 KB` |

Likely source categories:

- `index-*`: shared application/vendor/runtime chunk still exceeds the current
  warning limit.
- `heic2any-*`: very large HEIC conversion dependency. It is dynamically
  imported in `frontend/src/utils/heicConverter.js`, but it is also statically
  imported by upload surfaces such as `frontend/src/components/ui/FileUpload.jsx`
  and `frontend/src/components/dermatology/PhotoUploader.jsx`.
- `AdminPanel-*`: large role panel. Route-level lazy loading already exists,
  but the panel itself remains a high-cost route chunk.
- `DentistPanelUnified-*`, `AnalyticsPage-*`, `RegistrarPanel-*`: large role or
  analytics surfaces that should be split only by bounded workflow slices.

Do not fix this by increasing `chunkSizeWarningLimit`; that would hide the
signal instead of reducing runtime cost.

### P2 - Dynamic/Static Import Overlap

Vite reports that `frontend/src/utils/errorHandler.js` is dynamically imported
by `frontend/src/api/interceptors.js` but also statically imported by these
runtime consumers:

- `frontend/src/components/payment/PaymentWidget.jsx`
- `frontend/src/hooks/usePayments.js`
- `frontend/src/hooks/useRoles.js`
- `frontend/src/hooks/useUsers.js`
- `frontend/src/pages/CardiologistPanelUnified.jsx`
- `frontend/src/pages/CashierPanel.jsx`
- `frontend/src/pages/LabPanel.jsx`
- `frontend/src/pages/RegistrarPanel.jsx`
- `frontend/src/pages/UserProfile.jsx`
- `frontend/src/pages/VisitDetails.jsx`
- `frontend/src/pages/auth/ChangePasswordRequired.jsx`

Because the module is already statically imported, the dynamic import in
`api/interceptors.js` cannot move it to a separate chunk. The current behavior
works, but the import strategy is misleading and keeps generating noise.

## Recommended PR Slices

### PR-PERF-2 - Error Handler Import Cleanup

Goal: remove the Vite dynamic/static overlap warning without changing error
handling behavior.

Candidate change:

- Replace the dynamic `await import('../utils/errorHandler')` in
  `frontend/src/api/interceptors.js` with a static import, or make the module
  consistently lazy only if every static consumer can remain untouched.

Validation:

- `cd frontend; npm.cmd run lint:check`
- `cd frontend; npm.cmd run build`
- Browser smoke for one API error path if a safe fixture exists.

Stop condition:

- Stop if the change alters toast timing, token refresh flow, silent request
  behavior, or centralized error logging.

### PR-PERF-3 - HEIC Conversion Boundary Review

Goal: keep HEIC conversion off unrelated initial/route chunks and preserve file
upload behavior.

Candidate review targets:

- `frontend/src/utils/heicConverter.js`
- `frontend/src/components/ui/FileUpload.jsx`
- `frontend/src/components/dermatology/PhotoUploader.jsx`

Validation:

- targeted FileUpload tests if present
- browser upload smoke with non-HEIC and mocked HEIC path
- `cd frontend; npm.cmd run build`

Stop condition:

- Stop if the slice changes accepted file types, image conversion output,
  dermatology photo workflow, or patient file upload semantics.

### PR-PERF-4 - AdminPanel Route Chunk Split Plan

Goal: reduce the large `AdminPanel-*` route chunk by splitting one admin surface
at a time.

Candidate direction:

- Inventory active AdminPanel sub-surfaces from `routeRegistry.js` that all map
  to `AdminPanel`.
- Pick one admin-only, low-risk sub-view as the first lazy child boundary.
- Keep RBAC and route ownership unchanged.

Validation:

- authenticated admin browser smoke for `/admin`
- route-specific smoke for the chosen admin sub-view
- `cd frontend; npm.cmd run lint:check`
- `cd frontend; npm.cmd run build`

Stop condition:

- Stop if a split changes route registry behavior, role gating, or admin data
  loading order.

### PR-PERF-5 - Specialty Panel Chunk Plan

Goal: reduce the large specialty panel chunks without changing clinical
workflow semantics.

Candidate direction:

- Split only optional, tab-specific heavy panels after a clinical workflow
  review.
- Keep current patient, visit, report, and print flows intact.

Validation:

- authenticated specialty browser smoke for affected route
- keyboard/focus route smoke
- build size comparison

Stop condition:

- Stop if the slice changes patient selection, visit identity, print payload,
  lab/EMR semantics, or clinical status wording.

## Current Safety Decision

This PR intentionally does not change:

- `frontend/vite.config.js`
- `frontend/src/api/interceptors.js`
- runtime imports
- route registry
- role panels
- upload/photo/file conversion code
- package dependencies

The safest next implementation is PR-PERF-2 because it targets a single warning
source and has a small behavior-preserving proof surface.

## Validation

Commands run:

```powershell
cd frontend
npm.cmd run build
cd ..
Get-ChildItem frontend\dist\assets -Filter *.js | Sort-Object Length -Descending | Select-Object -First 12
rg -n "errorHandler" frontend\src
```

Report quality checks for this PR should remain docs-only:

```powershell
git diff --check
```
