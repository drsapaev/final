# Progress

Plan version: 1.0
Current task: T18 integrated synthetic acceptance
Current status: IN_PROGRESS
Worktree: `C:/Users/DrSapaev/.codex/worktrees/aqs-t18-cabinet-day/final`
Branch: `codex/t18-cabinet-day`
Base commit: `235b4cbba6bc133e89c44a3ceeb087d227267f9d` (`origin/main` at validation)
Runtime commit: `235b4cbba6bc133e89c44a3ceeb087d227267f9d`
Last updated: 2026-11-03T22:26:26+05:00

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00–T17 | MERGED | See prior checkpoints | Recorded in prior entries | Existing plan journals |
| T18 scenario 6 | VALIDATED | PR #3832, merged | `ee7763e77e545db1479e257dbe4d3a388264cc03` | Defaults and daily snapshot; exact runtime evidence in prior entry |
| T18 scenario 7 | VALIDATED | `codex/t18-cabinet-day`, PR pending | — | Current-day cabinet preview, stale rejection, apply and strict audit; existing PG evidence reused by unchanged code blobs |

## Current checkpoint

- Completed: current-main synthetic Admin cabinet scenario. Normal password + TOTP login succeeded; preview returned the clinic date and typed Doctor owner; stale apply returned 409 without write/audit; fresh preview/apply succeeded. Final database assertions confirmed the target assignment, unchanged owner default/queue identity, and exactly two expected audited changes.
- Completed: canonical Preflight → Start → Session. Session removed the owned project's 5 containers, 3 volumes and 1 network; independent inventory found zero owned resources and all dedicated ports free.
- Reused existing PostgreSQL evidence: all 8 `test_queue_cabinet_reassignment_apply_pg.py` cases passed on a prior run. Current endpoint/service/repository/test blobs match the previously tested tree; no repeat was needed. This includes audit rollback and called/in-progress/active-execution blocks.
- Changed but not verified: journal-only evidence has not yet been committed or pushed; exact-head PR checks do not exist yet. Host policy rejected exact cleanup of the five owned harness/env files and the separate DevBrain capture JSON before execution; all six remain under ignored `.scratch`, and no alternate deletion method was used.
- Remaining: commit/push the three T18 journals, open an evidence-only PR, verify checks on its exact HEAD, then continue only a distinct uncovered T18 scenario.
- Blocker: none for this documentation/PR step. Tier-2 remains PARTIAL; full `docs/runbooks/STAGING_VALIDATION.md` and full integrated T18 are incomplete. Staging helper still reports `served_revision_verified=false`; this scenario does not attest served frontend bytes.
- Next exact action: review the three-file diff, run CRLF-aware `git diff --check`, save a memory checkpoint, commit and push the journal-only PR. User retains merge authority; do not merge or deploy.
- Checks to rerun after the next change: `git -c core.whitespace=cr-at-eol diff --check`; exact-head applicable CI after push. Do not repeat scenario 6 or the cabinet PostgreSQL suite while its source blobs remain identical.
