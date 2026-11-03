# Progress

Plan version: 1.0
Current task: T18 integrated synthetic acceptance
Current status: IN_PROGRESS
Worktree: `C:/Users/DrSapaev/.codex/worktrees/aqs-t18-cabinet-day/final`
Branch: `codex/t18-cabinet-day`
Base commit: `235b4cbba6bc133e89c44a3ceeb087d227267f9d` (`origin/main` at validation)
Runtime commit: `235b4cbba6bc133e89c44a3ceeb087d227267f9d`
Last updated: 2026-11-03T23:48:00+05:00

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00–T17 | MERGED | See prior checkpoints | Recorded in prior entries | Existing plan journals |
| T18 scenario 1 | VALIDATED | `codex/t18-cabinet-day`, PR #3861 open | — | 24 backend contract tests plus live synthetic Admin/TOTP setup; hidden profile and two same-specialty typed targets confirmed |
| T18 scenario 6 | VALIDATED | PR #3832, merged | `ee7763e77e545db1479e257dbe4d3a388264cc03` | Defaults and daily snapshot; exact runtime evidence in prior entry |
| T18 scenario 7 | VALIDATED | `codex/t18-cabinet-day`, [PR #3861](https://github.com/drsapaev/final/pull/3861) open, Ready for review | — | Current-day cabinet preview, stale rejection, apply and strict audit; existing PG evidence reused by unchanged code blobs |
| T18 scenario 8 | VALIDATED | `codex/t18-cabinet-day`, PR #3861 open | — | Current-main PostgreSQL token/GraphQL last-slot races plus availability, QR and queue-limits remaining-quota tests |
| T18 scenario 9 | VALIDATED | `codex/t18-cabinet-day`, PR #3861 open | — | Current-main exact retry, lost-response replay, no double count, rollback, partial success/replay and partial rollback |

## Current checkpoint

- Completed: current-main synthetic Admin cabinet scenario (T18 scenario 7). Normal password + TOTP login succeeded; preview returned the clinic date and typed Doctor owner; stale apply returned 409 without write/audit; fresh preview/apply succeeded. Final database assertions confirmed the target assignment, unchanged owner default/queue identity, and exactly two expected audited changes.
- Completed: canonical Preflight → Start → Session. Session removed the owned project's 5 containers, 3 volumes and 1 network; independent inventory found zero owned resources and all dedicated ports free.
- Reused existing PostgreSQL evidence: all 8 `test_queue_cabinet_reassignment_apply_pg.py` cases passed on a prior run. Current endpoint/service/repository/test blobs match the previously tested tree; no repeat was needed. This includes audit rollback and called/in-progress/active-execution blocks.
- T18 scenarios 8–9: seven current-main PostgreSQL integration tests passed against one isolated disposable local PostgreSQL 17.11 instance; seven quota/status/API unit tests passed. PostgreSQL evidence covers token and GraphQL last-slot races, exact retry, lost-response replay, rollback and partial-batch conservation. Unit evidence covers public/QR availability and remaining-quota reporting. No runtime or tracked test files changed.
- T18 scenario 1: `test_queue_admin_directions_read_model.py` plus `test_multi_doctor_same_specialty_isolation.py` passed 24/24 on temporary SQLite fixtures; 6 warnings. A subsequent live synthetic Admin flow passed: ordinary password login, initial TOTP enrollment and a separate password+TOTP login; two active synthetic cardiology doctors; one new hidden QueueProfile; backend read model returned both typed doctor targets and `effectiveAvailability=available`, while public setting and public availability remained false. The clinic-day read returned zero existing queues; no queue or patient admission was created. One initial attempt failed because the scratch harness generated a numeric profile key disallowed by the UI pattern; correcting the harness key produced the passing run. This was a harness failure, not a product defect.
- Completed: scenario 8–9 journal evidence is committed and pushed to existing PR #3861 as `b730531a510d6f306f870ff469ca6e52d459e4c5`; its description now includes the current evidence and required labeled fields.
- Confirmed: on PR HEAD `94efa74787fa1891afadaf54e70f4068447fd84e`, every applicable exact-head check passed; path-aware backend/frontend/integration/readiness jobs were skipped for the documentation-only changes.
- Completed: scenario 1 related backend tests and journal evidence are committed/pushed to PR #3861 at `ec6bc5877d2fbb48de7f4832a667e00b6cc72505`; the PR description separates backend PASS from live Admin NOT_RUN.
- Confirmed: on exact PR HEAD `ec6bc5877d2fbb48de7f4832a667e00b6cc72505`, PR Required Gate, PR Review Quality Gate, CI Scope, lifecycle, Python/TypeScript/Actions analysis, security, Gitleaks, GitGuardian, scratch guards, notifications and CodeQL passed. Path-aware build/test/readiness jobs were skipped for documentation-only changes.
- Completed: live scenario 1 evidence was committed and pushed to PR #3861 at `315628d98e3112ee0ad047c8a2012ca0ee011111`; PR description now records the corrected live PASS and harness-only first failure. On that exact HEAD, applicable PR/quality/scope/lifecycle, security, Gitleaks, GitGuardian, scratch-guard and CodeQL checks passed. Backend/frontend/build/integration/readiness jobs were skipped for the documentation-only diff, not counted as passed.
- Remaining: PR #3861 awaits user-owned merge. The full integrated T18 matrix and `docs/runbooks/STAGING_VALIDATION.md` remain incomplete. Prior evidence for scenarios 2–5 and 10 is on separate commit-anchored slices and has not been reconciled against refreshed `main`.
- Blocker: user-owned merge of #3861 is pending. Tier-2 remains PARTIAL; no deferral is accepted. `served_revision_verified=false` remains unresolved and this scenario does not attest frontend bytes.
- Next exact action: user merges PR #3861. Then confirm the merge commit, create a fresh isolated worktree from current `origin/main`, reconcile scenarios 2–5 and 10, and select only a distinct remaining T18 gap. Do not repeat scenarios 1 or 6–9. User retains merge authority; do not merge or deploy.
- Checks to rerun after the next change: exact-head applicable CI. Do not repeat scenarios 6–9 or the cabinet PostgreSQL suite while their source blobs remain unchanged.
