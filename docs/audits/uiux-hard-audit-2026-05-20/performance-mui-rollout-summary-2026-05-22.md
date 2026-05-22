# Performance/MUI Rollout Summary

Date: 2026-05-22

This report closes the cyclic Performance/MUI rollout that followed the UI/UX
hard audit and the earlier third-cycle performance/MUI checklist. The goal was
to improve visibility, prevent new MUI runtime debt, choose one safe bundle
target, and land one narrow runtime bundle slice without changing clinic
contracts.

## Completed Cycle Checklist

- [x] PR-PERF-0: bundle baseline report.
- [x] PR-MUI-GATE-0: no-new-MUI runtime gate.
- [x] PR-PERF-1: initial bundle target decision.
- [x] PR-PERF-2: first runtime bundle slice.
- [x] Final: rollout completion summary.

## Merged PRs

| PR | Title | Result |
| --- | --- | --- |
| #1142 | `docs(frontend): refresh bundle performance baseline` | Merged |
| #1143 | `ci(frontend): prevent new mui runtime imports` | Merged |
| #1144 | `docs(frontend): plan initial bundle reduction target` | Merged |
| #1145 | `perf(frontend): reduce initial bundle slice` | Merged |

## What Changed

- Added a fresh bundle baseline report for the current Vite build.
- Added `frontend/scripts/audit-no-mui-runtime.mjs` and the
  `npm run audit:no-mui-runtime` gate.
- Wired the no-new-MUI audit into the existing frontend CI lint/audit block.
- Documented the first safe bundle target:
  `TelegramMiniAppPatientShell` extraction from the initial app shell.
- Moved the Telegram Mini App patient shell into its own lazy route module:
  `frontend/src/pages/TelegramMiniAppPatientShell.jsx`.
- Updated source-inspection guardrail tests to inspect the new module location.

## Final MUI Runtime Count

Current runtime MUI scan:

```text
npm run audit:no-mui-runtime
No-new-MUI runtime gate passed: 0 MUI imports/usages in pages/components.
```

Manual source scan also returned no matches for:

```text
@mui
@material-ui
Mui
```

within:

```text
frontend/src/pages
frontend/src/components
```

## Final Top JS Chunks

Fresh build command:

```text
cd frontend
npm run build
```

Top JavaScript assets after PR #1145:

| Asset | Size |
| --- | ---: |
| `index-D_6pYuU_.js` | 1384.58 KiB |
| `heic2any-A3fuQvc6.js` | 1320.46 KiB |
| `AdminPanel-BP5RahHi.js` | 971.77 KiB |
| `DentistPanelUnified-CBa1vxUb.js` | 247.82 KiB |
| `RegistrarPanel-BjfG921c.js` | 247.05 KiB |
| `AnalyticsPage-DpD3i3JA.js` | 246.05 KiB |
| `canonicalVisit-BTTTQSz3.js` | 171.28 KiB |
| `DermatologistPanelUnified-_o29gkAu.js` | 127.13 KiB |
| `panelPrint-BjbNl9Im.js` | 107.93 KiB |
| `LabPanel-4JEtl0fg.js` | 60.76 KiB |
| `index-Cinygqi8.js` | 58.60 KiB |
| `CashierPanel-CBi4bFHP.js` | 50.70 KiB |
| `AIChatWidget-BvZj0PND.js` | 48.87 KiB |
| `EnhancedAppointmentsTable-CeidiGLC.js` | 48.56 KiB |
| `ServiceCatalog-DRiigYhg.js` | 46.59 KiB |
| `CardiologistPanelUnified-Cmy1ahCd.js` | 46.04 KiB |
| `MediLabDemo-CL3QiPjg.js` | 39.78 KiB |
| `TelegramMiniAppPatientShell-Di59NWux.js` | 39.50 KiB |
| `UserProfile-B2K1xPGP.js` | 38.66 KiB |
| `DoctorPanel-BoivxOwt.js` | 37.49 KiB |

## Bundle Impact

The first runtime slice reduced the initial app shell by moving the Telegram
Mini App patient route into a dedicated lazy route chunk.

Measured before/after evidence:

| Asset | Before | After |
| --- | ---: | ---: |
| Initial `index-*` JS | 1423.89 KiB | 1384.58 KiB |
| Telegram Mini App patient route chunk | Included in initial bundle | 39.50 KiB lazy chunk |

The result is intentionally modest and low risk. It avoids broad route
refactors, preserves route registry component ownership, and keeps Telegram
Mini App behavior in the same source logic with only the lazy boundary moved.

## Remaining Performance Risks

- The initial `index-*` bundle is still large and should remain visible in
  future bundle reviews.
- `heic2any-*` remains a large isolated lazy chunk and should only be optimized
  through a dedicated HEIC upload-flow plan.
- `AdminPanel-*` is below the previous 1000 KiB target but remains a major
  admin-only chunk.
- Specialty panel chunks should not be split further without route, role,
  clinical-data, and browser proof.
- A hard bundle-size CI budget is still deferred until the baseline stabilizes
  for several frontend PRs.

## Not Changed

- No backend code, schema, API contract, RBAC, payment, queue, EMR, lab, or
  Telegram business behavior was intentionally changed.
- No `chunkSizeWarningLimit` increase was used to hide warnings.
- No MUI package or historical documentation mention was removed.
- No broad AdminPanel, specialty-panel, payment, or queue refactor was included.

## Validation Evidence

Local validation across the cycle included:

- `npm run build`
- `npm run audit:no-mui-runtime`
- `npm run lint:check`
- Targeted Telegram Mini App guardrail tests after the lazy route extraction
- Route ownership enforcement test
- Browser smoke for `/telegram/mini-app/patient`
- `git diff --check`

GitHub checks were green before each PR was merged.

## Next Optional Backlog

- Dependency category split for more precise CI execution.
- Security-sensitive category split for stricter high-risk workflow routing.
- Route-level lazy-load review for one safe route family at a time.
- HEIC upload flow-specific optimization plan.
- Bundle budget gate only after the current baseline proves stable.
- Branch protection review to keep the stable aggregate gate required.
