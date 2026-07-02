# Vite Performance Warning Plan

Date: 2026-05-20

Scope: refreshed report-only baseline for PR-PERF-9 after the initial Vite
performance remediation series. No runtime code, Vite config, imports, routes,
tests, backend, or deployment behavior changed in this PR.

## Baseline Command

```powershell
cd frontend
npm.cmd run build
```

Result: build passed.

Observed build stats:

- Vite `6.4.2`
- Modules transformed: `14003`
- Build time: `22.47s`
- Current `chunkSizeWarningLimit`: `1500` KB in `frontend/vite.config.js`
- Current status: no Vite chunk-size warning was emitted by this fresh build.

## Current Post-PR #953 Baseline

Largest generated JavaScript assets from the current build:

| Asset | Vite output size | File inventory size |
| --- | ---: | ---: |
| `index-CazkqJZm.js` | `1428.57 kB` | `1395.09 KiB` |
| `heic2any-BMTjW7cf.js` | `1352.15 kB` | `1320.46 KiB` |
| `AdminPanel-Chz2uih-.js` | `1046.32 kB` | `1021.80 KiB` |
| `AnalyticsPage-CrEGWH88.js` | `251.76 kB` | `245.86 KiB` |
| `RegistrarPanel-ChcO8dVR.js` | `251.58 kB` | `245.68 KiB` |
| `DentistPanelUnified--PA25ywr.js` | `249.43 kB` | `243.58 KiB` |
| `canonicalVisit-T0GWzPIQ.js` | `170.84 kB` | `166.84 KiB` |
| `DermatologistPanelUnified-B5FQ6rOB.js` | `128.84 kB` | `125.82 KiB` |
| `panelPrint-yQI5uZpS.js` | `110.52 kB` | `107.93 KiB` |
| `listItemTextClasses-BWZ33xTL.js` | `97.88 kB` | `95.59 KiB` |
| `LabPanel-1xF8dBkh.js` | `61.16 kB` | `59.73 KiB` |
| `index-Bh7KdqUj.js` | `60.00 kB` | `58.60 KiB` |

The current build has moved the previous oversized initial chunk under the
configured warning limit without increasing `chunkSizeWarningLimit`.

## Resolved Warning Sources

### P1 - Oversized JavaScript Chunk Warning

Historical PR-PERF-1 baseline:

| Historical asset | Historical size |
| --- | ---: |
| `index-BYQkHiui.js` | `1732.33 KB` |
| `heic2any-BJtmzsQg.js` | `1320.09 KB` |
| `AdminPanel-Om2b9RoN.js` | `1100.97 KB` |

Current result:

- `index-*` is now below the `1500` KB warning threshold.
- `heic2any-*` remains large but is isolated as a lazy conversion chunk.
- `AdminPanel-*` remains the largest route panel chunk, but is also below the
  warning threshold and has already had several optional child views split out.

Do not fix future bundle pressure by increasing `chunkSizeWarningLimit`; that
would hide the signal instead of reducing runtime cost.

### P2 - Dynamic/Static Import Overlap

Historical PR-PERF-1 warning:

- `frontend/src/utils/errorHandler.js` was dynamically imported by
  `frontend/src/api/interceptors.js` while also being statically imported by
  runtime consumers.

Current result:

- PR-PERF-2 / #947 removed the misleading dynamic/static import overlap.
- The fresh build does not emit the previous `errorHandler.js` overlap warning.

## Remediation Completed So Far

- PR-PERF-2 / #947: removed `errorHandler.js` dynamic/static import overlap.
- PR-PERF-3 / #948: lazy-loaded the HEIC conversion boundary.
- PR-PERF-4 / #949: split admin GraphQL explorer into a lazy child boundary.
- PR-PERF-5 / #950: split dentistry reports into a lazy child boundary.
- PR-PERF-6 / #951: lazy-loaded utility route components.
- PR-PERF-7 / #952: lazy-loaded admin queue profiles.
- PR-PERF-8 / #953: lazy-loaded admin service catalog.

## Remaining Performance Watchlist

### P1 - AdminPanel Route Chunk

`AdminPanel-*` is now below the Vite warning limit, but it remains a large
admin route chunk at roughly `1046.32 kB` in Vite output.

Recommended next slice:

- Split one additional low-risk, admin-only optional child view.
- Prefer read-only/reporting-heavy surfaces before mutation-heavy or
  security-sensitive surfaces.
- Keep RBAC, route ownership, data loading semantics, and admin behavior
  unchanged.

Stop condition:

- Stop if the candidate owns user/RBAC, payment, queue, Telegram, security,
  route guard, or mutation-heavy behavior.

### P2 - HEIC Conversion Chunk

`heic2any-*` remains intentionally large at roughly `1352.15 kB`, but it is a
lazy conversion dependency rather than an unrelated initial route cost.

Recommended next action:

- Leave it isolated unless upload route browser proof shows it blocks non-HEIC
  workflows.

Stop condition:

- Stop if a change alters accepted file types, image conversion output,
  dermatology photo workflow, or patient file upload semantics.

### P2 - MUI Runtime Debt

MUI-related chunks such as `listItemTextClasses-*`, `Select-*`, `TextField-*`,
`MenuItem-*`, and related component chunks still show that MUI remains a runtime
compatibility layer.

Recommended next action:

- Refresh `frontend/MUI_RUNTIME_INVENTORY.md`.
- Classify remaining references as runtime, example-only, admin-sensitive, or
  clinical/payment/queue-adjacent before any migration.

Stop condition:

- Do not mass-migrate MUI or remove the dependency while runtime imports exist.

## Recommended PR Slices

### PR-PERF-10 - One More AdminPanel Optional Boundary

Goal: reduce `AdminPanel-*` further through one low-risk optional child view.

Validation:

- `cd frontend; npm.cmd run test:run -- src/routing/__tests__/routeOwnershipEnforcement.test.js`
- `cd frontend; npm.cmd run lint:check`
- `cd frontend; npm.cmd run build`
- asset inventory comparison

### PR-PERF-11 - Reporting/Analytics Optional Boundary

Goal: split one additional reporting or analytics child view only if route and
RBAC proof remains behavior-identical.

Validation:

- same checks as PR-PERF-10
- authenticated admin route smoke if a local auth harness is available

### PR-MUI-1 - MUI Runtime Inventory Refresh

Goal: update the MUI inventory after the current performance changes.

Validation:

- `rg -l "@mui|Mui" frontend/src/pages frontend/src/components`
- docs-only diff proof
- `git diff --check`

## Current Safety Decision

This PR intentionally does not change:

- `frontend/vite.config.js`
- runtime imports
- route registry
- role panels
- upload/photo/file conversion code
- package dependencies

The safest next implementation is PR-PERF-10 because it can target one
admin-only optional child boundary while preserving the current below-threshold
Vite build.

## Validation

Commands run:

```powershell
cd frontend
npm.cmd run build
cd ..
Get-ChildItem frontend\dist\assets -Filter *.js | Sort-Object Length -Descending | Select-Object -First 20
```

Report quality checks for this PR should remain docs-only:

```powershell
git diff --check
py -3 scripts\check_pr_review_template.py --body-file <body-file>
```
