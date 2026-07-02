# AdminPanel Post-Split Review

Date: 2026-05-20

Scope: PR-PERF-12 review-only decision after the third-cycle AdminPanel bundle
splits. No frontend runtime code, route registry, RBAC, API client, backend,
test, Vite config, or package behavior changed in this review.

## Build Evidence

Command:

```powershell
cd frontend
npm.cmd run build
```

Result: build passed.

Observed build stats:

- Vite `6.4.2`
- Modules transformed: `14003`
- Build time: `1m 5s`
- Current `chunkSizeWarningLimit`: `1500` KB in `frontend/vite.config.js`
- Current status: no Vite chunk-size warning was emitted.

Largest current JavaScript assets by file inventory:

| Asset | Size |
| --- | ---: |
| `index-*` | `1400.99 KiB` |
| `heic2any-*` | `1320.46 KiB` |
| `AdminPanel-*` | `970.11 KiB` |
| `AnalyticsPage-*` | `245.86 KiB` |
| `RegistrarPanel-*` | `245.68 KiB` |
| `DentistPanelUnified-*` | `243.58 KiB` |
| `canonicalVisit-*` | `166.84 KiB` |
| `DermatologistPanelUnified-*` | `125.82 KiB` |
| `panelPrint-*` | `107.93 KiB` |
| `listItemTextClasses-*` | `95.59 KiB` |

## AdminPanel Split Status

The AdminPanel chunk is now below the third-cycle target:

- Current Vite output: `993.40 kB`
- Current file inventory: `970.11 KiB`

Completed AdminPanel optional child boundaries:

- `GraphQLExplorer`
- `QueueProfilesManager`
- `ServiceCatalog`
- `UnifiedReports`
- `WaitTimeAnalytics`

## Candidate Review

The next remaining static AdminPanel child views were reviewed only for
ownership and risk. They should not be split further in this cycle without a
fresh handoff or a narrower product reason.

| Candidate | Decision | Reason |
| --- | --- | --- |
| `AIAnalytics` | Stop | AI-adjacent analytics; needs AI-specific route/data review before touching. |
| `SystemManagement` | Stop | System monitoring/backups are operationally sensitive. |
| `CloudPrintingManager` | Stop | Printing configuration and job behavior need dedicated browser and workflow proof. |
| `MedicalEquipmentManager` | Stop | Clinical operations/equipment surface; avoid casual bundle-only change. |
| `UnifiedTelegramManagement` | Stop | Telegram integration is security/token/contract sensitive. |
| `UnifiedFinance` | Stop | Finance/payment-adjacent behavior is explicitly out of scope for bundle cleanup. |
| `ClinicManagement` | Stop | Clinic settings may affect operational configuration. |
| `AnalyticsDashboard` | Defer | Low-risk only if a future route audit proves the AdminPanel query-section path is still active and worth optimizing. |

## Decision

Stop AdminPanel bundle splitting in this third cycle.

Reason:

- The target is already met: `AdminPanel-*` is below `1000 KiB` by file
  inventory and below `1000 kB` in Vite output.
- Remaining candidates are sensitive enough that further lazy boundaries would
  be scope creep for this cycle.
- The next safer debt is MUI inventory and classification, not more AdminPanel
  runtime splitting.

## Next Smallest Step

Proceed to PR-MUI-1:

- Refresh `frontend/MUI_RUNTIME_INVENTORY.md`.
- Classify remaining MUI refs as runtime, example-only, admin-sensitive,
  clinical-heavy, payment/queue-adjacent, Telegram/AI-sensitive, or safe
  candidate.
- Do not migrate MUI in the inventory PR.

## Validation

Commands run:

```powershell
cd frontend
npm.cmd run build
cd ..
Get-ChildItem frontend\dist\assets -Filter *.js | Sort-Object Length -Descending | Select-Object -First 20
rg -n "AIAnalytics|SystemManagement|CloudPrintingManager|MedicalEquipmentManager|AnalyticsDashboard|ClinicManagement|UnifiedTelegramManagement|UnifiedFinance" frontend\src\pages\AdminPanel.jsx
```

Docs-only PR checks:

```powershell
git diff --check
py -3 scripts\check_pr_review_template.py --body-file <body-file>
```
