# Progress

Plan version: 1.0
Current task: T18 integrated synthetic acceptance
Current status: IN_PROGRESS
Worktree: `C:/Users/DrSapaev/.codex/worktrees/aqs-t18-cabinet-day/final`
Branch: `codex/t18-cabinet-day`
Base commit: `235b4cbba6bc133e89c44a3ceeb087d227267f9d` (`origin/main` at validation)
Runtime commit: `235b4cbba6bc133e89c44a3ceeb087d227267f9d`
Last updated: 2026-11-04T00:24:16+05:00

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00–T17 | MERGED | See prior checkpoints | Recorded in prior entries | Existing plan journals |
| T18 scenario 1 | VALIDATED | `codex/t18-cabinet-day`, PR #3861 open | — | 24 backend contract tests plus live synthetic Admin/TOTP setup; hidden profile and two same-specialty typed targets confirmed |
| T18 scenario 2 | PARTIAL | Prior live slice on #3805; source reconciliation pending | — | Doctorless service/resource archive tested; resource-only onboarding and no-extra-doctor path not fully proven |
| T18 scenario 3 | PARTIAL | PR #3763 merged | `e2c4e0335bd1bd8bfc15db23e70436c82b53b39c` | Parent-conflict repair slice passed; broad incomplete-configuration/next-action coverage remains partial |
| T18 scenario 4 | VALIDATED | PR #3805 merged | `e7cf5b47b1aa96e5df0b9baf9e9e567b8e3fecbf` | Live hidden/publish/hide/republish/permanent-address/resource lifecycle passed; relevant current-main paths unchanged |
| T18 scenario 5 | PARTIAL | Current-main source; PR #3861 evidence update | — | Unit guards 11/11 PASS; current-source PostgreSQL direct-token/resource-token targets NOT_RUN; no live revalidation |
| T18 scenario 6 | VALIDATED | PR #3832, merged | `ee7763e77e545db1479e257dbe4d3a388264cc03` | Defaults and daily snapshot; exact runtime evidence in prior entry |
| T18 scenario 7 | VALIDATED | `codex/t18-cabinet-day`, [PR #3861](https://github.com/drsapaev/final/pull/3861) open, Ready for review | — | Current-day cabinet preview, stale rejection, apply and strict audit; existing PG evidence reused by unchanged code blobs |
| T18 scenario 8 | VALIDATED | `codex/t18-cabinet-day`, PR #3861 open | — | Current-main PostgreSQL token/GraphQL last-slot races plus availability, QR and queue-limits remaining-quota tests |
| T18 scenario 9 | VALIDATED | `codex/t18-cabinet-day`, PR #3861 open | — | Current-main exact retry, lost-response replay, no double count, rollback, partial success/replay and partial rollback |
| T18 scenario 10 | PARTIAL | PR #3805 merged | `e7cf5b47b1aa96e5df0b9baf9e9e567b8e3fecbf` | Setup-context return/history/reload slice passed; all legacy URLs, special profile key and explicit 409 guard not all proven |

## Current checkpoint

- Completed: current-main synthetic Admin cabinet scenario (T18 scenario 7). Normal password + TOTP login succeeded; preview returned the clinic date and typed Doctor owner; stale apply returned 409 without write/audit; fresh preview/apply succeeded. Final database assertions confirmed the target assignment, unchanged owner default/queue identity, and exactly two expected audited changes.
- Completed: canonical Preflight → Start → Session. Session removed the owned project's 5 containers, 3 volumes and 1 network; independent inventory found zero owned resources and all dedicated ports free.
- Reused existing PostgreSQL evidence: all 8 `test_queue_cabinet_reassignment_apply_pg.py` cases passed on a prior run. Current endpoint/service/repository/test blobs match the previously tested tree; no repeat was needed. This includes audit rollback and called/in-progress/active-execution blocks.
- T18 scenarios 8–9: seven current-main PostgreSQL integration tests passed against one isolated disposable local PostgreSQL 17.11 instance; seven quota/status/API unit tests passed. PostgreSQL evidence covers token and GraphQL last-slot races, exact retry, lost-response replay, rollback and partial-batch conservation. Unit evidence covers public/QR availability and remaining-quota reporting. No runtime or tracked test files changed.
- T18 scenario 5 current-main unit guard tests: `test_queue_token_parent_recheck.py` and `test_qr_available_specialists.py` passed 11/11 (2 warnings). Three targeted PostgreSQL old-token/resource-token cases remain `NOT_RUN`: the isolated fixture did not reach Alembic head and fell back to a schema-less database; no test body ran and no product defect is inferred.
- T18 scenario 1: `test_queue_admin_directions_read_model.py` plus `test_multi_doctor_same_specialty_isolation.py` passed 24/24 on temporary SQLite fixtures; 6 warnings. A subsequent live synthetic Admin flow passed: ordinary password login, initial TOTP enrollment and a separate password+TOTP login; two active synthetic cardiology doctors; one new hidden QueueProfile; backend read model returned both typed doctor targets and `effectiveAvailability=available`, while public setting and public availability remained false. The clinic-day read returned zero existing queues; no queue or patient admission was created. One initial attempt failed because the scratch harness generated a numeric profile key disallowed by the UI pattern; correcting the harness key produced the passing run. This was a harness failure, not a product defect.
- Cleanup: canonical staging teardown was previously verified. The user removed the private synthetic `staging.env` and four remaining task-owned scratch files. The temporary PostgreSQL test containers were stopped/removed; its database used tmpfs only, no persistent volume remains, and port 15561 is closed.
- Completed: scenario 8–9 journal evidence is committed and pushed to existing PR #3861 as `b730531a510d6f306f870ff469ca6e52d459e4c5`; its description now includes the current evidence and required labeled fields.
- Confirmed: on PR HEAD `94efa74787fa1891afadaf54e70f4068447fd84e`, every applicable exact-head check passed; path-aware backend/frontend/integration/readiness jobs were skipped for the documentation-only changes.
- Completed: scenario 1 related backend tests and journal evidence are committed/pushed to PR #3861 at `ec6bc5877d2fbb48de7f4832a667e00b6cc72505`; the PR description separates backend PASS from live Admin NOT_RUN.
- Confirmed: on exact PR HEAD `ec6bc5877d2fbb48de7f4832a667e00b6cc72505`, PR Required Gate, PR Review Quality Gate, CI Scope, lifecycle, Python/TypeScript/Actions analysis, security, Gitleaks, GitGuardian, scratch guards, notifications and CodeQL passed. Path-aware build/test/readiness jobs were skipped for documentation-only changes.
- Completed: live scenario 1 evidence was committed and pushed to PR #3861 at `315628d98e3112ee0ad047c8a2012ca0ee011111`; PR description now records the corrected live PASS and harness-only first failure. On that exact HEAD, applicable PR/quality/scope/lifecycle, security, Gitleaks, GitGuardian, scratch-guard and CodeQL checks passed. Backend/frontend/build/integration/readiness jobs were skipped for the documentation-only diff, not counted as passed.
- Confirmed: PR #3861 remains OPEN / Ready / CLEAN at HEAD `f83ee906852c4ec9dc8068cbff25f012587cd070`; all applicable exact-head checks passed. Documentation-only backend/frontend/integration/readiness jobs were skipped, not counted as passed.
- Remaining: PR #3861 awaits user-owned merge. T18 scenarios 2, 3, 5 and 10 remain partial; scenario 4 is accepted from source-reconciled live evidence. Full integrated T18, `docs/runbooks/STAGING_VALIDATION.md`, and served frontend byte provenance remain incomplete.
- Blocker: user-owned merge of #3861 is pending. Tier-2 remains PARTIAL; no deferral is accepted. `served_revision_verified=false` remains unresolved and this scenario does not attest frontend bytes.
- Next exact action: user merges PR #3861. Then confirm the merge commit, create a fresh isolated worktree from current `origin/main`, and prepare one combined synthetic validation cycle for the remaining scenario 2/5/10 gaps. Do not repeat scenarios 1 or 6–9. User retains merge authority; do not merge or deploy.
- Checks to rerun after the next change: exact-head applicable CI. Do not repeat scenarios 6–9 or the cabinet PostgreSQL suite while their source blobs remain unchanged.
