# Progress

Plan version: 1.0
Current task: T01
Current status: PR_OPEN
Worktree: `C:\final\_wt_aqs_t01`
Branch: `codex/aqs-T01-profile-modal`
Base commit: `bae927f5c88010808d9091e7f47d09bbfdfa1005`
Current commit: `6b8f2b7e9`
Last updated: 2026-09-30T16:24:44+05:00

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00 | MERGED | `codex/aqs-T00-docs` / [PR #3536](https://github.com/drsapaev/final/pull/3536) | `bae927f5c88010808d9091e7f47d09bbfdfa1005` | `EVIDENCE.md#t00` |
| T01 | PR_OPEN | `codex/aqs-T01-profile-modal` / [PR #3537](https://github.com/drsapaev/final/pull/3537) | | `EVIDENCE.md#t01` |
| T02 | PLANNED | | | |
| T03 | PLANNED | | | |
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

- Completed: T00 plan and ledgers merged as PR #3536 (`bae927f5...`); local main fast-forwarded to fresh `origin/main`; T00 worktree and branch cleaned; T01 implementation/evidence pushed and PR #3537 opened.
- Changed and locally validated: filter reads the Select's value callback; profile form uses the shared Dialog with Escape, focus trap and return; labels are associated; presets are valid API hex; the UI baseline ratchet passes after moving the static palette into a small admin-local `.ts` constants module and removing an extra theme branch. 13 focused tests, type-check, scoped ESLint, stylelint, build and ratchet pass.
- Remaining: wait for corrected PR #3537 checks/review, fix any red check in the same PR, merge, then clean the branch/worktree and sync main before T02.
- Blocker: none. T01 must not change profile business semantics or API contract.
- Next exact action: monitor regenerated PR #3537 checks and merge only after all required checks are green.
- Checks to rerun after the next change: focused Vitest, type-check, scoped ESLint/stylelint, build, `git diff --check`, applicable pre-commit hooks, PR checks.
