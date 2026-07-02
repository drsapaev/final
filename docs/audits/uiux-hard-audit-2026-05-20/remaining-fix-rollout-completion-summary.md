# Remaining UI/UX Hard Audit Fix Rollout Completion Summary

Date: 2026-05-20

Scope: second small-PR cycle after the initial UI/UX hard-audit rollout.

## Outcome

The second cycle completed as small PRs from fresh `origin/main`. Each PR stayed
inside a single UI, QA, policy, or report surface and merged only after green
GitHub checks.

No backend API, database migration, RBAC, route registry, payment, queue, EMR,
lab business logic, Telegram, notification, production secret, package, or
deployment behavior was intentionally changed.

## Merged PRs

| Step | PR | Title | Merge commit |
| --- | ---: | --- | --- |
| PR-10 | #936 | `docs: add remaining ui ux rollout checklist` | `7ce1710f` |
| PR-UX-10 | #937 | `fix(frontend): remove invalid notification aria role warnings` | `8c5efc30` |
| PR-UX-11 | #938 | `fix(frontend): share specialty appointment summary bar` | `aaa1fe5c` |
| PR-UX-12 | #939 | `test(frontend): extend authenticated ui qa smoke` | `1ac573d4` |
| PR-UX-13 | #940 | `test(frontend): add authenticated rbac denial smoke` | `d6a6a864` |
| PR-UX-14 | #941 | `fix(frontend): clarify registrar workflow hierarchy` | `bd919bf3` |
| PR-UX-15 | #942 | `fix(frontend): improve patient panel readability` | `7f63240a` |
| PR-UX-16 | #943 | `fix(frontend): improve lab panel visual accessibility` | `661a0608` |
| PR-UX-17 | #944 | `docs(frontend): document mui migration decision` | `80580442` |
| PR-PERF-1 | #945 | `docs(frontend): report vite performance warnings` | `e7b8d1ba` |

## Completed Work

- Added the second-cycle rollout checklist and kept it updated.
- Removed invalid ARIA `role` warnings in the notification code path by
  renaming internal role data away from DOM `role` semantics.
- Shared the repeated specialty appointment summary/action-bar pattern through
  `AppointmentSummaryBar`.
- Extended authenticated UI smoke coverage for role and specialty panels.
- Added negative RBAC denial smoke coverage for protected role routes.
- Improved Registrar workflow hierarchy with a compact worklist header.
- Improved Patient panel readability, unavailable-data copy, and semantic empty
  states.
- Improved Lab panel main landmark, heading, tablist/tab/tabpanel semantics,
  keyboard tab navigation, live status messages, and empty collection
  resilience.
- Refreshed MUI island inventory and documented that no additional low-risk MUI
  runtime island is safe to migrate without a dedicated handoff.
- Added a Vite performance warning baseline and next-PR plan for large chunks
  and the `errorHandler.js` dynamic/static import overlap.

## Validation Evidence

- Every PR merged after GitHub Actions required checks were green.
- Frontend runtime PRs ran local `npm.cmd run lint:check` and
  `npm.cmd run build` before push.
- Browser/Playwright validation covered affected routes and viewports:
  - specialty summary bar routes
  - authenticated Admin, Doctor, Cashier, Lab, Patient, and specialty routes
  - negative RBAC denial routes
  - `/registrar`
  - `/patient/payments`
  - `/lab`
- Lab browser smoke specifically covered `375x812`, `768x1024`, `1280x800`,
  and `1920x1080` plus keyboard tab navigation.
- Docs-only PRs ran `git diff --check` and PR body template validation.
- PR-PERF-1 ran a local Vite build to record current warning evidence.

## Remaining Unknowns

- Existing unrelated lint warnings remain outside the touched slices.
- Vite still reports large chunks; PR-PERF-1 intentionally planned, not fixed,
  the follow-up implementation.
- `errorHandler.js` still has dynamic/static import overlap until a dedicated
  performance PR changes `frontend/src/api/interceptors.js`.
- HEIC conversion and large route panels remain performance-sensitive and need
  their own bounded reviews.
- MUI runtime/example references remain in 14 files; remaining runtime targets
  are not low-risk without separate domain review.
- Browser QA used local/authenticated harnesses, not production data or secrets.

## Recommended Next Backlog

1. PR-PERF-2: remove the `errorHandler.js` dynamic/static import overlap while
   preserving token refresh, toast, silent request, and error logging behavior.
2. PR-PERF-3: review HEIC conversion boundaries around `heic2any`, FileUpload,
   and dermatology photo upload.
3. PR-PERF-4: split one AdminPanel sub-surface after route/RBAC proof.
4. PR-PERF-5: split one specialty panel optional tab only after clinical
   workflow review.
5. Migrate one remaining MUI island only with a dedicated first-touch file,
   domain stop conditions, and browser proof.
6. Continue UI/UX fixes only as one role, route, state family, or policy surface
   per PR.

## Final Status

The second-cycle checklist is complete after this summary PR merges into
`main`. Local and cloud `main` should be synced after merge, and no second-cycle
work branches should remain open.
