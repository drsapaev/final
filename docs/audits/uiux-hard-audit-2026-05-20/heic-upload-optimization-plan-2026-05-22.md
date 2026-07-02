# HEIC Upload Optimization Plan

Date: 2026-05-22

Scope: report-only HEIC upload flow plan. No runtime code, frontend code,
backend code, tests, dependencies, Vite config, service worker code, upload
contracts, RBAC, route registry, or clinical workflow behavior changed.

## Why This Plan Exists

The current performance baseline still shows `heic2any-*` as a large generated
JavaScript asset. That size is visible in build output, but the source review
shows it is already isolated behind a lazy conversion boundary. A safe
optimization must therefore focus on upload-flow evidence and regression guards,
not a broad rewrite.

## Files Inspected

- `frontend/src/utils/heicConverter.js`
- `frontend/public/sw.js`
- `frontend/src/components/ui/FileUpload.jsx`
- `frontend/src/components/dermatology/PhotoUploader.jsx`
- `frontend/src/components/ui/__tests__/FileUpload.test.jsx`
- `frontend/src/pages/DermatologistPanelUnified.jsx`
- `frontend/src/routing/routeRegistry.js`
- `docs/audits/uiux-hard-audit-2026-05-20/bundle-performance-baseline-2026-05-22.md`
- `docs/audits/uiux-hard-audit-2026-05-20/performance-mui-rollout-summary-2026-05-22.md`
- `docs/audits/uiux-hard-audit-2026-05-20/vite-performance-warning-plan.md`

## Fresh Build Evidence

Command:

```powershell
cd frontend
npm.cmd run build
```

Result: build passed.

Relevant Vite output:

| Asset | Vite output size | Meaning |
| --- | ---: | --- |
| `heicConverter-CChBQFb_.js` | `1.51 kB` | Small shared HEIC helper chunk |
| `heic2any-A3fuQvc6.js` | `1352.15 kB` | Large lazy fallback converter chunk |
| `DermatologistPanelUnified-_o29gkAu.js` | `130.18 kB` | Dermatology route panel chunk |
| `index-D_6pYuU_.js` | `1417.81 kB` | Initial app shell |
| `AdminPanel-BP5RahHi.js` | `995.09 kB` | Admin route panel chunk |

The large `heic2any-*` asset remains a separate lazy chunk. It is not part of
the dermatology route panel chunk or the initial app shell.

## Current HEIC Architecture

### Main Thread Converter

`frontend/src/utils/heicConverter.js` exports:

- `isHEICFile(file)`
- `convertHEICToJPEG(heicFile, quality)`
- `convertMultipleFiles(files, quality)`
- `getImageInfo(file)`
- `createImagePreview(file)`
- `checkHEICSupport()`
- `handleFileInputWithHEICConversion(event, callback)`

The main converter first tries a service worker conversion path. If that fails,
it calls a fallback function that dynamically imports `heic2any`:

```js
const heic2any = (await import('heic2any')).default;
```

This confirms the app bundle already defers the heavy dependency until the
fallback conversion path is needed.

### Service Worker Converter

`frontend/public/sw.js` listens for `CONVERT_HEIC` messages and dynamically
imports:

```js
https://cdn.skypack.dev/heic2any
```

This keeps the dependency out of the app bundle for the service-worker-first
path, but it creates a separate offline/security/reliability question. That
question should be handled as a dedicated service worker hardening slice, not a
bundle-size cleanup.

## Runtime Entry Points

| Entry point | Status | Notes |
| --- | --- | --- |
| `/doctor/dermatology` | Active | `DermatologistPanelUnified` renders `PhotoUploader` on the photos tab when a current appointment or selected patient exists. |
| `frontend/src/components/dermatology/PhotoUploader.jsx` | Active | Accepts JPG/PNG/HEIC, checks `isHEICFile(file)`, converts only HEIC/HEIF files, and uploads to `/visits/{visitId}/files`. |
| `frontend/src/components/ui/FileUpload.jsx` | Shared component | Accepts HEIC/HEIF and calls the same converter only after `isHEICFile(file)` returns true. No active runtime page import was found in `frontend/src/pages`, but it remains a reusable UI component with tests. |
| `frontend/src/components/ui/__tests__/FileUpload.test.jsx` | Test coverage | Covers HEIC conversion, but currently imports and mocks `heic2any` directly. |

Route registry proof:

- Route id: `doctor-dermatology`
- Path: `/doctor/dermatology`
- Roles: `Admin`, `Doctor`, `derma`
- Owner: `clinical.dermatology`
- Component: `DermatologistPanelUnified`

## Risk Assessment

Do not remove `heic2any` in a performance PR. It is required for HEIC fallback
conversion.

Do not change:

- accepted file types or extension/MIME detection
- HEIC/HEIF to JPEG output type
- generated JPEG filename semantics
- dermatology photo upload endpoint
- `FormData` fields: `file`, `kind`, `visit_id`, `metadata`
- upload status, conversion status, or error semantics
- route registry ownership
- RBAC or protected route behavior

The service worker CDN import is a real follow-up risk, but it is not the same
as initial bundle weight. Treat it as offline/security/runtime reliability work.

## Recommended Small PR Slices

### PR-HEIC-1 - Test Boundary Guard

Goal: prove non-HEIC uploads do not trigger the HEIC fallback dependency and
that HEIC uploads still use the converter boundary.

Preferred scope:

- `frontend/src/components/ui/__tests__/FileUpload.test.jsx`
- optional narrow converter test if an existing utility test file already fits

Validation:

```powershell
cd frontend
npm.cmd run test:run -- src/components/ui/__tests__/FileUpload.test.jsx
npm.cmd run build
Get-ChildItem dist\assets -Filter *heic*
```

Stop if the test requires changing upload behavior.

### PR-HEIC-2 - PhotoUploader Guard Coverage

Goal: add or strengthen proof that `PhotoUploader` calls conversion only for
HEIC/HEIF files and leaves JPG/PNG upload behavior untouched.

Preferred scope:

- `frontend/src/components/dermatology/PhotoUploader.jsx`
- existing dermatology/photo uploader tests if present, or a narrow new test

Validation:

```powershell
cd frontend
npm.cmd run lint:check
npm.cmd run build
```

Add browser QA for `/doctor/dermatology` only when the authenticated QA harness
can open the photos tab without weakening auth.

### PR-HEIC-3 - Service Worker Reliability Plan

Goal: decide whether the service worker should continue importing
`https://cdn.skypack.dev/heic2any` or use a local/offline-safe strategy.

Preferred scope:

- docs/report first
- no service worker runtime change until security, offline, and browser proof
  are clear

Validation:

```powershell
git diff --check
```

Stop if the change would silently alter conversion semantics or cache behavior.

## Immediate Decision

Do not attempt a broad runtime optimization in the next PR. The heavy app
dependency is already lazy-loaded and route-isolated. The safest next step is
PR-HEIC-1: add targeted test evidence around the conversion boundary so future
changes cannot accidentally make non-HEIC uploads pay for `heic2any`.

## Validation Plan For Future Runtime Work

- `cd frontend; npm.cmd run test:run -- src/components/ui/__tests__/FileUpload.test.jsx`
- `cd frontend; npm.cmd run lint:check`
- `cd frontend; npm.cmd run build`
- `Get-ChildItem frontend\dist\assets -Filter *heic*`
- browser smoke for the affected upload route and viewport
- `git diff --check`

## Stop Conditions

- Backend endpoint, schema, RBAC, route contract, or upload contract changes are
  needed.
- Accepted file types or clinical photo metadata would change.
- The fix requires removing `heic2any` instead of guarding when it loads.
- Browser/auth proof is required but cannot run without weakening auth.
- A service worker change would create offline or CDN dependency ambiguity
  without a separate hardening plan.
