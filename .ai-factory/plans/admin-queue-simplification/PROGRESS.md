# Progress

Plan version: 1.0
Current task: T03
Current status: PR_OPEN
Worktree: `C:\final\_wt_aqs_t03_cabinet_read`
Branch: `codex/aqs-T03-cabinet-read`
Base commit: `b4ba6320797f056da19bbdc5cc672b3a97d2091e`
Current commit: `66e3d9fc0ef0066554bf895ed358c29621bd3df5` (OpenAPI freshness correction; T03 test follow-up is currently uncommitted)
Last updated: 2026-10-01T02:06:49+05:00

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00 | MERGED | `codex/aqs-T00-docs` / [PR #3536](https://github.com/drsapaev/final/pull/3536) | `bae927f5c88010808d9091e7f47d09bbfdfa1005` | `EVIDENCE.md#t00` |
| T01 | MERGED | `codex/aqs-T01-profile-modal` / [PR #3537](https://github.com/drsapaev/final/pull/3537) | `967bd398c14bce4b835bd5be1205532387e2a909` | `EVIDENCE.md#t01` |
| T02 | MERGED | `codex/aqs-T02-queue-settings-state` / [PR #3538](https://github.com/drsapaev/final/pull/3538) | `b4ba6320797f056da19bbdc5cc672b3a97d2091e` | `EVIDENCE.md#t02` |
| T03 | PR_OPEN | `codex/aqs-T03-cabinet-read` / [PR #3540](https://github.com/drsapaev/final/pull/3540) | | `EVIDENCE.md#t03` |
| T04 | PLANNED | | | |
| T05 | PLANNED | | | |
| T06 | PLANNED | | | |
| T07 | PLANNED | | | |
| T08 | PLANNED | | | |
| T09 | PLANNED | | | |
| T10 | PLANNED | | | |
| T11 | PLANNED | | | |
| T12 | PLANNED | | | |
| T13 | PLANNED | | | |
| T14 | PLANNED | | | |
| T15 | PLANNED | | | |
| T16 | PLANNED | | | |
| T17 | PLANNED | | | |
| T18 | PLANNED | | | |

## Current checkpoint

- Completed: T00–T02 merged; PR #3538 merged as `b4ba6320797f056da19bbdc5cc672b3a97d2091e`. T02's formal Tier 2 deferral acknowledgment was recorded before merge. Tier 2 backend-dependent specs remain `NOT_RUN`; they are not represented as passed.
- Changed and validated in T02: queue-settings loading/save protection, stale draft conflict metadata, logout isolation, correct dirty state after edits during save, defensive storage access, and removal of fabricated controls. See `EVIDENCE.md#t02` for separate local and GitHub validation snapshots.
- T03 scope: cabinet read contract only. The current patch defaults an omitted day to clinic-local today, returns typed queue owner and default cabinet alongside the saved day assignment, derives displayed statistics from the same filtered read, treats changed defaults as informational, and distinguishes load failure from empty results.
- Completed in T03: backend tests 14/14; final component tests 3/3; full Vitest 2,877/2,877; type-check; scoped ESLint; direct pinned Stylelint; theme and icon audits; production build; UI baseline ratchet; strict locale parity; OpenAPI/frontend-type generation; post-commit generated-types parity; PR body gate (19 checks). Code commit: `e9448bca543fcb98595c63ef086fdfeb47a8dd52`.
- Changed but not verified: a test-only follow-up passes `clinic_day` explicitly to the existing cabinet sync command so the read test remains deterministic across UTC/Tashkent date boundaries. Local execution is `NOT_RUN` because no test `DATABASE_URL` is configured and isolated PostgreSQL port 55432 is stopped. The failed Frontend E2E job is rerunning on the previous SHA.
- Remaining: commit and push the deterministic test follow-up and updated evidence; await the new full GitHub check set; resolve any remaining red Tier 1 checks in PR #3540.
- Blocker: full CI on head `66e3d9fc` failed once in the backend suite because the test's sync request omitted its day while the queue used clinic-local today; the write path defaults to host-local `date.today()`. The previous CI attempt also failed an unrelated Lab dirty-guard E2E timeout; that exact job is being rerun. Backend failure caused required parity to be skipped. Merge requires green Tier 1 CI and an applicable formal Tier 2 decision for this PR. Staging timing and backend-dependent Tier 2 E2E are `NOT_RUN`.
- Next exact action: record the explicit-day test correction, commit/push it to PR #3540, then monitor the full checks and E2E rerun.
- Checks to rerun after the next change: focused backend integration test (when disposable PostgreSQL is available), `git diff --check`, and all GitHub PR checks for the new head.
