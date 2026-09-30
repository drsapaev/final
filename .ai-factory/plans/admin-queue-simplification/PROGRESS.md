# Progress

Plan version: 1.0
Current task: T03
Current status: IN_PROGRESS
Worktree: `C:\final\_wt_aqs_t03_cabinet_read`
Branch: `codex/aqs-T03-cabinet-read`
Base commit: `b4ba6320797f056da19bbdc5cc672b3a97d2091e`
Current commit: `e9448bca543fcb98595c63ef086fdfeb47a8dd52` (T03 code committed; docs-only PR checkpoint remains)
Last updated: 2026-10-01T01:25:51+05:00

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00 | MERGED | `codex/aqs-T00-docs` / [PR #3536](https://github.com/drsapaev/final/pull/3536) | `bae927f5c88010808d9091e7f47d09bbfdfa1005` | `EVIDENCE.md#t00` |
| T01 | MERGED | `codex/aqs-T01-profile-modal` / [PR #3537](https://github.com/drsapaev/final/pull/3537) | `967bd398c14bce4b835bd5be1205532387e2a909` | `EVIDENCE.md#t01` |
| T02 | MERGED | `codex/aqs-T02-queue-settings-state` / [PR #3538](https://github.com/drsapaev/final/pull/3538) | `b4ba6320797f056da19bbdc5cc672b3a97d2091e` | `EVIDENCE.md#t02` |
| T03 | IN_PROGRESS | `codex/aqs-T03-cabinet-read` | | `EVIDENCE.md#t03` |
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
- Changed but not verified: GitHub CI/Playwright and first-screen browser timing. The exact `lint:check` wrapper failed locally because Stylelint was absent from PATH after the ESLint stage passed; the pinned cached Stylelint 16.26.1 run passed directly. `git diff --check` passed after final code and ledger edits.
- Remaining: update this checkpoint, remove the untracked PR-body scratch file, push the branch, open PR, and wait for required GitHub checks.
- Blocker: none for opening the T03 PR. Merge still requires green Tier 1 CI and formal acknowledgment if Tier 2 remains deferred. Staging timing is `NOT_RUN`; T02 Tier 2 is also `NOT_RUN`.
- Next exact action: make a docs-only checkpoint commit with the PR-cycle state, then push and open the PR using the already validated PR body.
- Checks to rerun after the next change: `git diff --check`; after the docs checkpoint, verify clean tracked status and push the code plus checkpoint commits.
