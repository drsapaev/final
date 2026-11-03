# Progress

Plan version: 1.0
Current task: T18 integrated synthetic acceptance
Current status: IN_PROGRESS
Worktree: `C:/Users/DrSapaev/.codex/worktrees/aqs-t18-cabinet-day/final`
Branch: `codex/t18-cabinet-day`
Base commit: `235b4cbba6bc133e89c44a3ceeb087d227267f9d` (`origin/main` at validation)
Runtime commit: `235b4cbba6bc133e89c44a3ceeb087d227267f9d`
Last updated: 2026-11-03T22:50:00+05:00

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00–T17 | MERGED | See prior checkpoints | Recorded in prior entries | Existing plan journals |
| T18 scenario 6 | VALIDATED | PR #3832, merged | `ee7763e77e545db1479e257dbe4d3a388264cc03` | Defaults and daily snapshot; exact runtime evidence in prior entry |
| T18 scenario 7 | VALIDATED | `codex/t18-cabinet-day`, [PR #3861](https://github.com/drsapaev/final/pull/3861) open, Ready for review | — | Current-day cabinet preview, stale rejection, apply and strict audit; existing PG evidence reused by unchanged code blobs |
| T18 scenario 8 | VALIDATED | `codex/t18-cabinet-day`, PR #3861 open | — | Current-main PostgreSQL token/GraphQL last-slot races plus availability, QR and queue-limits remaining-quota tests |
| T18 scenario 9 | VALIDATED | `codex/t18-cabinet-day`, PR #3861 open | — | Current-main exact retry, lost-response replay, no double count, rollback, partial success/replay and partial rollback |

## Current checkpoint

- Completed: current-main synthetic Admin cabinet scenario. Normal password + TOTP login succeeded; preview returned the clinic date and typed Doctor owner; stale apply returned 409 without write/audit; fresh preview/apply succeeded. Final database assertions confirmed the target assignment, unchanged owner default/queue identity, and exactly two expected audited changes.
- Completed: canonical Preflight → Start → Session. Session removed the owned project's 5 containers, 3 volumes and 1 network; independent inventory found zero owned resources and all dedicated ports free.
- Reused existing PostgreSQL evidence: all 8 `test_queue_cabinet_reassignment_apply_pg.py` cases passed on a prior run. Current endpoint/service/repository/test blobs match the previously tested tree; no repeat was needed. This includes audit rollback and called/in-progress/active-execution blocks.
- T18 scenarios 8–9: seven current-main PostgreSQL integration tests passed against one isolated disposable local PostgreSQL 17.11 instance; seven quota/status/API unit tests passed. PostgreSQL evidence covers token and GraphQL last-slot races, exact retry, lost-response replay, rollback and partial-batch conservation. Unit evidence covers public/QR availability and remaining-quota reporting. No runtime or tracked test files changed.
- Completed: scenario 8–9 journal evidence is committed and pushed to existing PR #3861 as `b730531a510d6f306f870ff469ca6e52d459e4c5`; its description now includes the current evidence and required labeled fields.
- Changed but not verified: applicable exact-head checks are rerunning after the journal push and PR-body correction. The first body-triggered PR Review Quality Gate run failed because its required field labels were missing; the description was corrected and the gate rerun is pending.
- Remaining: confirm applicable checks on the latest exact HEAD. After the user-owned merge, reconcile prior evidence for scenarios 1–5 and 10, then continue only a distinct uncovered T18 slice.
- Blocker: none for this documentation/PR step. Tier-2 remains PARTIAL; full `docs/runbooks/STAGING_VALIDATION.md` and full integrated T18 are incomplete. Staging helper still reports `served_revision_verified=false`; this scenario does not attest served frontend bytes.
- Next exact action: verify applicable checks on the latest PR #3861 HEAD, then wait for the user-owned merge. After merge, reconcile prior evidence for scenarios 1–5 and 10. User retains merge authority; do not merge or deploy.
- Checks to rerun after the next change: exact-head applicable CI. Do not repeat scenarios 6–9 or the cabinet PostgreSQL suite while their source blobs remain unchanged.
