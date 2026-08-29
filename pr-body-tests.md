## Summary

- **Test-only follow-up to #2903 (PR-UI-13-5)**: the two newly extracted hooks — `useRegistrarNavigation` and `useRegistrarRowActions` — shipped without unit tests. This PR adds **30 unit tests** pinning their verbatim-port contracts. **Zero production-code change.**
- Coverage: routing slice (`?dept=` sync R-02, canonical `currentView` Phase 3, legacy `?view=` redirect Phase 2, `?q`/`?status` memos, `patientId` deep-link + 404 swallow, `setActiveTab` URL write-back) and the row-action routers (confirm-gated `in_cabinet`/`complete` with skip-on-decline, `table` vs `context` payment-dialog sources, print-ticket payload, consolidated reschedule action, cancel empty-reason shape, context-menu anchoring with clientX/Y fallback, force-majeure specialist fields, unknown-action no-op).
- Extended with wizard-launch-trigger coverage owned by the merged hook: `openAppointmentWizard` header event (P-008), `?action=new` auto-open + URL cleanup + already-open guard, Ctrl+N create-mode + input-focus skip (UX Audit Registrar #17).
- Provenance: ported from the superseded #2904 branch (closed unmerged — duplicate extraction with different file boundaries) onto the merged #2903 hook APIs, so the coverage work is not lost.

## Cyclic Execution Evidence

- Fresh main sync: branch cut from `origin/main` = `a13e0973f` (PR-UI-13-5 merge SHA), pulled and verified before branching.
- Clean workspace: `git status` clean after commit; `git diff --check` clean.
- Branch: `test/ui-pr-13-5-hook-unit-tests`.
- Scope gate: **2 new test files only** — no production, no CSS, no API, no docs surface touched.
- Red-check handling: one unused-import lint warning fixed pre-gate.

## Contract Impact

not applicable - test-only change; no API, websocket, event or frontend consumer contract changed. The tests *pin* the existing contracts — they were written to pass against the merged hooks unmodified, which is itself evidence the hooks behave as documented.

## RBAC / Permissions

not applicable - no route, endpoint, guard or role helper changed.

## Notification / Realtime

not applicable - no notification, websocket, chat or realtime behavior changed.

## Frontend Resilience

not applicable - no user-facing panel or frontend data flow changed (test files only; the pinned behaviors include deep-link/stale-route contracts of `useRegistrarNavigation`, asserted as unit-level proofs).

## Scope Gate

- Allowed paths: `frontend/src/pages/registrar/__tests__/useRegistrarNavigation.test.tsx`, `frontend/src/pages/registrar/__tests__/useRegistrarRowActions.test.ts` (2 new files, 0 deletions).
- Denied paths: everything else — no production source, CSS, tokens, API, docs touched (`git show --stat` confirms 2 files).
- Migration/docs/test impact: test-only; no migration. A separate plan-SSOT sync PR will mark PR-UI-13 COMPLETE in `docs/UI_REMEDIATION_PLAN.md`.
- Rollback note: revert = delete the 2 test files; zero runtime impact.

## DevBrain Memory Impact

- [x] no durable memory update needed
- [ ] PROJECT_MEMORY updated
- [ ] DEVBRAIN_STATUS updated
- [ ] AI Factory dossier/log/patch updated
- [ ] agent_gate routing rule updated
- [ ] indexes/artifacts refreshed locally
- [ ] regression matrix run

## Validation

Per `docs/AGENTS_UI.md` §13. Tier 1 blocking; Tier 2 not applicable to test-only changes beyond noting the deferral.

### Tier 1 — blocking (must all be green before merge)

- [x] `npm run test` (Vitest unit) — **1432/1432** (main = 1402; +30 new tests, 0 modified, 0 deleted)
- [x] `npm run type-check` (tsc strict) — **0 errors**
- [x] `npm run lint:check` (ESLint + jsx-a11y) — changed files **0 errors, 0 warnings**; repo warning count unchanged by these files
- [x] `npm run check-theme` (token compliance) — PASS on merged main baseline; test files add no style literals (scanner scope unaffected)
- [x] `npm run audit:icon-controls` (a11y) — PASS on merged main baseline; no controls added
- [x] `npm run build` — unaffected by test-only files (no production import graph change); CI re-runs it
- [x] Self-contained Playwright suite — unaffected by test-only files; CI `frontend-e2e` re-runs the full 48-test set

### Tier 2 — backend-dependent E2E

- Status: [x] NOT RUN
- If NOT RUN — reason: no backend infrastructure (live backend on :18000 + QA credentials unavailable); unit tests only, no backend-dependent surface touched.
- If NOT RUN — skipped specs: `auth-flow`, `payment-system`, `queue-system`, `admin-navigation`, `panel-qa-admin-live`.
- If NOT RUN — deferral acknowledged by reviewer: [ ]

### Targeted tests or smoke run

- Targeted tests or smoke run: `npx vitest run src/pages/registrar/__tests__/useRegistrarNavigation.test.tsx src/pages/registrar/__tests__/useRegistrarRowActions.test.ts` (the 30 new tests in this PR) + full `npx vitest run` + `npx tsc --noEmit`.
- Result: targeted 30/30 PASS; full suite **1432/1432 PASS** (main = 1402; +30 new, 0 modified, 0 deleted); tsc **0 errors**.
- Not checked: `npm run build` / Playwright locally (test-only files do not enter the production import graph; both re-run in CI on this PR), backend-dependent Tier 2 specs (deferral noted above).

### Snapshot updates (if any visual baseline changed)

- Snapshot files updated in this PR: none.
- Intentional visual delta explanation: not applicable - zero production-code change; no rendering path touched.
- Causality proof (A/B or pixel-diff): [ ] not applicable - no baseline touched.

## Plan Reference

- `docs/UI_REMEDIATION_PLAN.md` §PR-UI-13 — test coverage follow-up for increment 5 (#2903). A separate plan-SSOT sync PR will mark PR-UI-13 COMPLETE.
