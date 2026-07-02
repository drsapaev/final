# UI/UX Hard Audit Fix Rollout Completion Summary

Date: 2026-05-20

Scope: Small-PR UI/UX hard-audit rollout for the `2026-05-20` audit artifacts.

## Outcome

The rollout completed as a sequence of small, green PRs from fresh `origin/main`. The changes stayed inside the intended UI/report/policy surfaces and did not intentionally change backend APIs, database schema, RBAC, payment, queue, EMR, lab, Telegram, notification, or route contracts.

## Merged PRs

| Step | PR | Title | Merge commit |
| --- | ---: | --- | --- |
| PR-0 | #922 | `docs: add ui ux hard audit baseline` | `ccb794a7493469746885258e8d396293e8d34ba8` |
| PR-UX-1 | #924 | `fix(frontend): improve payment cancel accessibility` | `521fb42d59bcaeddd5b36508d58ae049269ad1ed` |
| PR-UX-2 | #925 | `fix(frontend): improve queue join recovery states` | `10899e0b1b972ff530b08f18c538b65ec15f151c` |
| PR-UX-3 | #926 | `test(frontend): add authenticated ui qa harness` | `af28e1ccba0405e7a0a2b47c2d7619474d76dbb1` |
| PR-UX-4 | #927 | `fix(frontend): improve cashier payment accessibility` | `b6fae6c23ccd386d26926e9157320d70f285888e` |
| PR-UX-5 | #928 | `fix(frontend): clarify doctor current patient workflow` | `7249202077c2c10785eab8b8d56d0bd4fbb3d670` |
| PR-UX-6 | #929 | `fix(frontend): reduce admin support legacy ui drift` | `7cfa175f73873dfd3679ce7ef5597e7a5acb663d` |
| PR-UX-7 | #930 | `fix(frontend): converge admin panel ui slice` | `b6e5fe94050414e84dc1c6d9ff5707e61518af9c` |
| PR-UX-8A | #931 | `fix(frontend): improve cardiology panel ui slice` | `634b937849bb138b727d1a2d0b40fcc62406b5de` |
| PR-UX-8B | #932 | `fix(frontend): improve dermatology panel ui slice` | `82e6732dacf447e55faabedb7ec7d3c8094f7e27` |
| PR-UX-8C | #933 | `fix(frontend): improve dentistry panel ui slice` | `4408e7e4e304da31bf1e67218836e2c91df5cf61` |
| PR-UX-9 | #934 | `docs(frontend): document mui island policy` | `303afca196e0fc2a195650ef7dc9cd35ab004a7b` |

## Validation Evidence

- Every PR was merged only after GitHub Actions reported green required checks.
- Frontend code PRs ran `npm run lint:check` and `npm run build` locally before push.
- Browser QA covered changed public or authenticated route surfaces:
  - `/payment/cancel`
  - `/queue/join`
  - `/admin`
  - `/clinical/appointments`
  - `/admin/audit`
  - `/admin/user-select`
  - `/cashier`
  - `/doctor`
  - `/doctor/cardiology`
  - `/doctor/dermatology`
  - `/doctor/dentistry`
- Specialty browser QA verified the new appointment summary/action-bar slices with authenticated fixtures, four summary items, and no horizontal overflow.
- `git diff --check` passed for each local PR slice; CRLF notices were non-blocking and did not indicate whitespace errors.
- PR body template validation passed for the PRs created in this rollout.

## Remaining Unknowns

- Existing lint warnings remain in unrelated files; this rollout did not attempt broad warning cleanup.
- Existing Vite build warnings about large chunks and dynamic/static imports remain; bundle splitting is still a future performance task.
- Preview browser QA still sees existing `_vercel/speed-insights` 404 console noise in local Vite preview; this was not caused by the UI slices.
- Negative RBAC paths were not exhaustively re-tested for every protected route because the changed slices did not modify route guards or permissions.
- MUI islands remain in 14 runtime or example files; PR-UX-9 documented policy/inventory only and did not migrate them.

## Next Backlog

1. Fix remaining invalid ARIA role lint warnings in role panels and notification tests as dedicated small PRs.
2. Add a reusable appointment summary/action-bar primitive if the three specialty slices prove stable in daily use.
3. Split large frontend chunks and review dynamic/static import overlap reported by Vite.
4. Migrate one low-risk MUI island at a time, following `frontend/MUI_RUNTIME_INVENTORY.md`.
5. Extend authenticated QA coverage from smoke fixtures into stable Playwright specs for Admin, Doctor, Cashier, Lab, and specialty panels.
6. Add negative RBAC browser checks for protected role routes without changing production auth behavior.

## Final Status

The rollout is complete after this summary PR merges into `main`. Future UI/UX work should continue with the same pattern: one role, route, state family, or policy surface per PR, backed by targeted validation and green GitHub Actions.
