# Bundle Performance Baseline

Date: 2026-05-22

Scope: PR-PERF-0 report-only baseline. No runtime code, route registry, Vite
config, frontend dependencies, backend code, CI, API, RBAC, payment, queue,
EMR, lab, Telegram, notification, or deployment behavior changed.

## Cycle Status

- [x] Fresh `origin/main` branch used for the baseline report.
- [x] Fresh frontend production build completed.
- [x] Top JavaScript assets recorded.
- [x] Runtime MUI inventory checked for `frontend/src/pages` and
  `frontend/src/components`.
- [x] No `chunkSizeWarningLimit` increase proposed.
- [x] No runtime optimization implemented in this docs-only PR.
- [ ] Next PR: add no-new-MUI runtime regression gate.
- [ ] Later PR: choose one initial bundle reduction target before editing
  runtime code.

## Baseline Commands

```powershell
cd frontend
npm.cmd run build
cd ..
Get-ChildItem frontend\dist\assets -Filter *.js |
  Sort-Object Length -Descending |
  Select-Object -First 20 @{Name='File';Expression={$_.Name}},@{Name='KiB';Expression={[math]::Round($_.Length / 1KB, 2)}}
rg -l "@mui|@material-ui|Mui" frontend/src/pages frontend/src/components
```

Result:

- `npm.cmd run build`: passed.
- Runtime MUI search: `0` matching files.

## Current Top JavaScript Assets

Fresh build inventory from `frontend/dist/assets`:

| Asset | Size |
| --- | ---: |
| `index-BlAk62rR.js` | `1423.89 KiB` |
| `heic2any-BadZ30Qs.js` | `1320.46 KiB` |
| `AdminPanel-CsIG3n58.js` | `971.77 KiB` |
| `DentistPanelUnified-BOR4Zy0d.js` | `247.82 KiB` |
| `RegistrarPanel-BjO9Dx6V.js` | `247.05 KiB` |
| `AnalyticsPage-IECpEQOW.js` | `246.05 KiB` |
| `canonicalVisit-Df82p9t8.js` | `171.28 KiB` |
| `DermatologistPanelUnified-BBZyiBIv.js` | `127.13 KiB` |
| `panelPrint-2Npsryb-.js` | `107.93 KiB` |
| `LabPanel-CR2uNXC1.js` | `60.76 KiB` |
| `index-OAzOHQ-2.js` | `58.60 KiB` |
| `CashierPanel-14xsS-yS.js` | `50.70 KiB` |
| `AIChatWidget-9-g_kVoL.js` | `48.87 KiB` |
| `EnhancedAppointmentsTable-D9H50chf.js` | `48.56 KiB` |
| `ServiceCatalog-Ch191prb.js` | `46.59 KiB` |
| `CardiologistPanelUnified-EQWNSYra.js` | `46.04 KiB` |
| `MediLabDemo-BO-jGmbO.js` | `39.78 KiB` |
| `UserProfile-fyc65nKo.js` | `38.66 KiB` |
| `DoctorPanel--tcv8GoN.js` | `37.49 KiB` |
| `QueueJoin-DUu1vWK9.js` | `35.88 KiB` |

## Decisions Locked By This Baseline

- `AdminPanel-*` is already below the previous local review target of
  `1000 KiB`. Do not continue casual `AdminPanel` splitting without a fresh,
  route-specific handoff.
- `heic2any-*` remains intentionally isolated as a lazy conversion chunk. Do
  not touch it without a dedicated HEIC upload/browser flow plan.
- `index-*` remains the best candidate area for future initial bundle review,
  but no runtime change should be made before identifying one small, safe
  target.
- Do not increase `frontend/vite.config.js` `chunkSizeWarningLimit`; that would
  hide bundle pressure instead of reducing it.
- Runtime MUI imports/usages in `frontend/src/pages` and
  `frontend/src/components` are currently at `0`; the next smallest useful
  action is a no-new-MUI regression gate.

## Next Safe Slices

1. PR-MUI-GATE-0: add a static no-new-MUI runtime gate and wire it into the
   existing frontend CI audit block.
2. PR-PERF-1: inspect current `index-*` contributors and choose one safe target
   for a future initial bundle reduction.
3. PR-PERF-2: implement only the chosen target, preferably through a lazy
   boundary or direct import cleanup, preserving all clinical and operational
   behavior.

## Stop Conditions

- Stop if an optimization requires backend/API/RBAC/payment/queue/EMR/lab
  behavior changes.
- Stop if a target touches auth, role ownership, route contracts, payment
  status semantics, queue ordering, clinical identity, or upload conversion
  semantics.
- Stop if the next candidate is too broad for one PR.
