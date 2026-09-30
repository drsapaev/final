# Progress

Plan version: 1.0
Current task: T03
Current status: PR_OPEN
Worktree: `C:\final\_wt_aqs_t03_cabinet_read`
Branch: `codex/aqs-T03-cabinet-read`
Base commit: `b4ba6320797f056da19bbdc5cc672b3a97d2091e`
Current commit: `2945d33e6c3ae1df500a4f098dbcf3b7dc5156d9` (T03 deterministic test follow-up; later commits are evidence checkpoints)
Last updated: 2026-10-01T02:32:26+05:00

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
- Completed in T03: local backend focus 14/14 before the final test-only adjustment; frontend component focus 3/3; full Vitest 2,877/2,877; type-check; scoped ESLint; direct pinned Stylelint; theme and icon audits; production build; UI baseline ratchet; strict locale parity; OpenAPI/frontend-type generation; post-commit generated-types parity; PR body gate (19 checks). Full GitHub Tier 1 CI passed on `2945d33e6c3ae1df500a4f098dbcf3b7dc5156d9`: backend, frontend unit/build/lint, Playwright E2E, OpenAPI freshness, parity, Code Quality, PR Required Gate, CodeQL, and gitleaks.
- Changed but not verified: local rerun of the final test-only follow-up was `NOT_RUN` because no test `DATABASE_URL` is configured and isolated PostgreSQL port 55432 is stopped. The full GitHub PostgreSQL backend suite passed. Synthetic-staging first-content timing and Tier 2 backend-dependent E2E remain `NOT_RUN`.
- Remaining: obtain/record the applicable formal Tier 2 deferral decision for PR #3540 before merge; then continue with T04 only after the T03 PR cycle closes.
- Blocker: no Tier 1 CI failures remain. Tier 2 E2E and first-screen staging timing are deferred/not run, and PR #3540's reviewer deferral checkbox remains blank. The user's latest technical approval referenced frontend-only PR #3538, already merged, and is not recorded as the T03 #3540 acknowledgment.
- Next exact action: wait for a formal Tier 2 deferral acknowledgment explicitly applying to PR #3540, or run the deferred backend-dependent checks when synthetic staging and QA credentials are available.
- Checks to rerun after the next change: if the deferral checkbox is updated, rerun the PR-body review gate and review the resulting GitHub checks; no code test rerun is needed unless code changes.
