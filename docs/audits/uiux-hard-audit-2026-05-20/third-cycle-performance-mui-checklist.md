# Third UI/UX Performance And MUI Debt Rollout Checklist

Date: 2026-05-20

This checklist starts the third small-PR cycle after the hard UI/UX audit,
the first UI/UX fix rollout, the second remaining-fixes rollout, and the
initial Vite performance remediation PRs.

## Rules

- Start every PR from fresh `origin/main`.
- Keep one PR limited to one performance boundary, one route child view, one
  MUI island, one report, or one policy surface.
- Use `clinic-ui-ux-master` first for clinic UI/UX and design-system safety.
- Use `vercel-react-best-practices` for bundle, lazy-loading, render, and
  performance slices.
- Preserve backend/API/RBAC/payment/queue/EMR/lab/Telegram/notification
  behavior unless a later plan explicitly scopes a contract change.
- Do not increase `chunkSizeWarningLimit` to hide bundle warnings.
- Do not mass-migrate MUI.
- Do not remove MUI dependencies until runtime imports reach `0`.
- Commit, push, open PR, wait for green GitHub checks, merge, sync `main`, then
  continue.
- If a check fails, fix that PR before moving to the next one.

## Baseline Already Merged

These PRs are already merged before this third-cycle checklist:

- [x] PR-PERF-2 / #947: remove `errorHandler.js` dynamic/static import overlap.
- [x] PR-PERF-3 / #948: lazy-load HEIC conversion boundary.
- [x] PR-PERF-4 / #949: split admin GraphQL explorer chunk.
- [x] PR-PERF-5 / #950: split dentistry reports chunk.
- [x] PR-PERF-6 / #951: lazy-load utility route components.
- [x] PR-PERF-7 / #952: lazy-load admin queue profiles view.
- [x] PR-PERF-8 / #953: lazy-load admin service catalog view.

Current local build evidence after PR-PERF-12 review:

| Asset | Approx size |
| --- | ---: |
| `index-*` | `1400.99 KiB` |
| `heic2any-*` | `1320.46 KiB` |
| `AdminPanel-*` | `970.11 KiB` |
| `AnalyticsPage-*` | `245.86 KiB` |
| `RegistrarPanel-*` | `245.68 KiB` |
| `DentistPanelUnified-*` | `243.58 KiB` |
| `ServiceCatalog-*` | `46.51 KiB` |
| `UnifiedReports-*` | `35.25 KiB` |
| `WaitTimeAnalytics-*` | `19.27 KiB` |

## Third-Cycle Backlog

- [x] PR-3-0: add this third-cycle performance/MUI debt checklist.
- [x] PR-PERF-9: update Vite performance warning docs with post-PR #953
  baseline and resolved warnings.
- [x] PR-PERF-10: split one additional low-risk `AdminPanel` optional child view
  into a lazy boundary.
- [x] PR-PERF-11: split one additional low-risk analytics/admin reporting child
  view only if route/RBAC proof stays behavior-identical.
- [x] PR-PERF-12: review whether `AdminPanel-*` can be reduced below `1000 KiB`
  with one more optional-view split; stop if the next candidate is
  user/RBAC/payment/queue/Telegram/security-sensitive.
- [x] PR-MUI-1: refresh `frontend/MUI_RUNTIME_INVENTORY.md` after current
  performance changes and classify remaining runtime/example MUI refs.
- [x] PR-MUI-2: decide no low-risk admin MUI island is eligible without
  route/browser proof and keep runtime UI unchanged.
- [x] PR-MUI-3: decide example-only MUI policy for `components/examples` without
  changing runtime UI.
- [x] PR-MUI-4: create a gated handoff for payment/queue/lab/dental/cardiology
  MUI islands; do not migrate them in the same PR as the handoff.
- [ ] Final: summarize third-cycle completion, merged PRs, remaining chunks, MUI
  status, and next backlog.

## Candidate Performance Slices

Preferred order:

1. Continue `AdminPanel` optional child boundaries where the component is
   admin-only and not the route guard, route registry, auth/RBAC layer, or data
   model owner.
2. Use read-only/reporting-heavy admin surfaces before mutation-heavy surfaces.
3. Keep analytics/report splitting separate from service/user/payment/Telegram
   splitting.
4. Keep specialty panel splitting to optional tabs only, never current patient,
   visit identity, print payload, lab/EMR semantics, or clinical status wording.

Possible first candidates, each requiring source inspection before editing:

- `AnalyticsDashboard`
- `WaitTimeAnalytics`
- `AIAnalytics`
- `UnifiedReports`
- `SystemManagement`
- `CloudPrintingManager`
- `MedicalEquipmentManager`

Do not treat these as automatically approved. Stop if inspection shows the
slice owns permissions, writes, side effects, payment/queue behavior, Telegram
state, security configuration, or clinical data semantics.

## MUI Debt Policy

MUI is still a legacy compatibility layer in this clinic frontend. The third
cycle should reduce or clarify MUI debt only through gated slices:

- [ ] Inventory before each MUI PR:
  `rg -l '@mui|Mui' frontend/src/pages frontend/src/components`
- [ ] Confirm whether the target is runtime, admin-sensitive, clinical-heavy,
  payment/queue-adjacent, Telegram/AI-sensitive, or example-only.
- [ ] Touch exactly one MUI island or one policy doc per PR.
- [ ] Prefer `frontend/src/components/ui/macos` and CSS variables.
- [ ] Prove no route, RBAC, payment, queue, EMR, lab, Telegram, notification, or
  backend contract changed.
- [ ] Run browser proof for the affected route when runtime UI changes.

Current no-go buckets unless a dedicated handoff approves them:

- Payment: `PaymentWidget.jsx`, `PaymentTest.jsx`
- Queue: `OnlineQueueManager.jsx`
- Lab: `LabReportGenerator.jsx`
- Cardiology: `ECGViewer.jsx`
- Dental: `TreatmentPlanner.jsx`, `ToothModal.jsx`
- Telegram/AI: `TelegramManager.jsx`, `MCPMonitor.jsx`
- Patient clinical data: `FamilyRelationsCard.jsx`

## Validation Baseline

For docs-only PRs:

- [ ] `git diff --check`
- [ ] PR body template gate:
  `py -3 scripts\check_pr_review_template.py --body-file <body-file>`
- [ ] Confirm docs-only diff.

For frontend performance PRs:

- [ ] `cd frontend; npm.cmd run test:run -- src/routing/__tests__/routeOwnershipEnforcement.test.js`
- [ ] `cd frontend; npm.cmd run lint:check`
- [ ] `cd frontend; npm.cmd run build`
- [ ] Asset inventory:
  `Get-ChildItem frontend\dist\assets -Filter *.js | Sort-Object Length -Descending | Select-Object -First 20`
- [ ] `git diff --check`
- [ ] GitHub Actions green before merge.

For runtime MUI PRs:

- [ ] All frontend performance PR checks above.
- [ ] Targeted browser/Playwright smoke for affected route and viewport.
- [ ] Static proof that no new `@mui` import was added.
- [ ] Static proof that only one MUI island was touched.

## Stop Conditions

- Stop if the slice requires backend contract, DB migration, route/RBAC
  semantics, payment logic, queue logic, EMR/lab data semantics, Telegram
  security/token behavior, or production secrets.
- Stop if a performance split changes data loading order in a way that can
  affect behavior.
- Stop if a MUI migration touches more than one component family.
- Stop if browser/auth proof is needed but cannot run without weakening auth.
- Stop if the next performance candidate is too broad for a single PR.

