# Remaining UI/UX Hard Audit Fix Rollout Checklist

Date: 2026-05-20

This checklist starts the second small-PR cycle for issues that remained after the first UI/UX hard-audit rollout.

## Rules

- Start every PR from fresh `origin/main`.
- Keep one PR limited to one role, route, state family, policy surface, or QA surface.
- Use `clinic-ui-ux-master` first when available; use `clinic-frontend-design` as the narrow fallback.
- Preserve backend/API/RBAC/payment/queue/EMR/lab/Telegram/notification behavior unless a later plan explicitly scopes a contract change.
- Do not mass-migrate MUI, large panels, or performance architecture.
- Commit, push, open PR, wait for green GitHub checks, merge, sync `main`, then continue.
- If a check fails, fix that PR before moving to the next one.

## Remaining Backlog

- [x] PR-UX-10: fix invalid ARIA role lint warnings in touched frontend surfaces.
- [x] PR-UX-11: promote the repeated specialty appointment summary/action-bar pattern into one reusable primitive, only if the current duplication stays behavior-identical.
- [x] PR-UX-12: extend authenticated QA harness into stable Playwright smoke specs for Admin, Doctor, Cashier, Lab, and specialty panels.
- [x] PR-UX-13: add negative RBAC browser checks for protected role routes without changing production auth behavior.
- [x] PR-UX-14: improve Registrar workflow hierarchy as one narrow visible slice.
- [x] PR-UX-15: improve Patient panel readability/accessibility as one narrow visible slice.
- [x] PR-UX-16: improve Lab panel visual/accessibility QA as one narrow visible slice.
- [x] PR-UX-17: migrate one low-risk MUI island or document why no low-risk runtime island is safe yet.
- [x] PR-PERF-1: report and plan Vite large chunk / dynamic-static import overlap remediation without changing runtime behavior.
- [x] Final: summarize second-cycle completion, remaining unknowns, and next backlog.

## Validation Baseline

- [ ] `git diff --check`
- [ ] frontend lint/build for frontend code PRs
- [ ] targeted browser QA for changed UI routes
- [ ] targeted Playwright command for QA-harness PRs
- [ ] GitHub Actions green before merge

## Stop Conditions

- Stop if a slice requires backend contract, DB migration, route/RBAC semantics, payment logic, queue logic, EMR/lab data semantics, or production secrets.
- Stop if a MUI migration touches more than one component family.
- Stop if a performance fix needs bundler architecture changes beyond a report-only PR.
- Stop if authenticated QA cannot run without weakening auth.
