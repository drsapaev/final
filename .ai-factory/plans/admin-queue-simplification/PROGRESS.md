# Progress

Plan version: 1.4
Execution permission: IMPLEMENTATION_ACTIVE — user resumed the full plan on 2026-10-01
Start here: [RESUME.md](RESUME.md), then this file and current-task EVIDENCE
Canonical plan: [codex-admin-queue-simplification.md](../codex-admin-queue-simplification.md)
Current task: T06.2
Current status: VALIDATED (runtime constructors wired; 54 focused tests pass; selected pre-commit hooks pass; PR not opened)
Last completed task: T06.1 — MERGED
Worktree: `C:\final\_wt_aqs_t062_creation_policy`
Branch: `codex/aqs-T06.2-creation-policy`
Base commit: `e8f585ab0a51e256fa638fe56c0582eff0bbafc6`
Current commit: `e8f585ab0a51e256fa638fe56c0582eff0bbafc6`
Last updated: 2026-10-01T21:16:20+05:00

> T00–T06.1 are confirmed MERGED. T06.2 is VALIDATED locally and awaits PR. #3543 staging deferral is separate and staging remains NOT_RUN. No feature-flag activation or production deploy is authorized.

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00 | MERGED | `codex/aqs-T00-docs` / [PR #3536](https://github.com/drsapaev/final/pull/3536) | `bae927f5c88010808d9091e7f47d09bbfdfa1005` | `EVIDENCE.md#t00` |
| T01 | MERGED | `codex/aqs-T01-profile-modal` / [PR #3537](https://github.com/drsapaev/final/pull/3537) | `967bd398c14bce4b835bd5be1205532387e2a909` | `EVIDENCE.md#t01` |
| T02 | MERGED | `codex/aqs-T02-queue-settings-state` / [PR #3538](https://github.com/drsapaev/final/pull/3538) | `b4ba6320797f056da19bbdc5cc672b3a97d2091e` | `EVIDENCE.md#t02` |
| T03 | MERGED | `codex/aqs-T03-cabinet-read` / [PR #3540](https://github.com/drsapaev/final/pull/3540) | `1e781da72bd927926b538b139a6c251cd09848b5` | `EVIDENCE.md#t03-merge-checkpoint` |
| T04 | MERGED | `codex/aqs-T04-empty-profiles` / [PR #3541](https://github.com/drsapaev/final/pull/3541) | `ecc14b05411c7e7b54efca2966416cd6a69df37c` | `EVIDENCE.md#t04-merge-checkpoint` |
| T05 | MERGED | `codex/aqs-T05-settings-cache` / [PR #3543](https://github.com/drsapaev/final/pull/3543) | `fd53206f03b0361de6fc345f53b2bacf4195845c` | `EVIDENCE.md#t05-merge-checkpoint` |
| T06.1 | MERGED | `codex/aqs-T06-policy-schema` / [PR #3545](https://github.com/drsapaev/final/pull/3545) | `e8f585ab0a51e256fa638fe56c0582eff0bbafc6` | `EVIDENCE.md#t06.1-merge-checkpoint` |
| T06.2 | VALIDATED | `codex/aqs-T06.2-creation-policy` | | `EVIDENCE.md#t06.2-final-validation-checkpoint` |
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

- Completed: T00–T05 and T06.1 MERGED. T06.1 added legacy-safe `policy_version` and `online_issued_count` columns/constraints without changing constructors. PR #3545 merged at `e8f585ab0a51e256fa638fe56c0582eff0bbafc6` after explicit user authorization; live GitHub state confirmed MERGED.
- T05 review/merge: exact reviewed head `c04f41021bef5f8c306b9668cbb1c4b9afef2cc1`; runtime source unchanged since `47276d178972226b0bcf561bdf8fa26a6940b913`; merge `fd53206f03b0361de6fc345f53b2bacf4195845c` at 2026-10-01T16:24:40+05:00. Reviewed and merged trees match. Applicable backend/quality/contract/security gates passed; skipped path-aware jobs are not passed. No GitHub author-approval review was fabricated.
- Deferral: accepted for #3543/T05 by agent decision under the user's explicit delegation. Full requirement/reason/evidence/owner/resume/headline fields are in DECISIONS and `EVIDENCE.md#t05-merge-checkpoint`. Local PG integration, synthetic staging/admin/queue E2E and cold/repeat timing remain NOT_RUN. The executing AQS agent owns resumption at T18/pre-deploy; T06's mandatory disposable-PG upgrade is not waived.
- Validation after merge: six focused queue unit files passed on `fd53206f` — 24 passed, 1 warning, Python 3.11.9 and isolated SQLite fixture. This is not PostgreSQL/staging proof. Earlier source lint/compile/hook results and baseline formatting limitations remain in timestamped T05 evidence.
- Base/cleanup: production checkout was clean `main` and fast-forwarded to `fd53206f`. No production process restarted, data queried, feature flag toggled or deployment settings changed. T05 runtime branch removed locally/remotely; detached worktree retained with untracked scratch. Earlier T03 local documents/scratch remain untouched.
- Documentation checkpoint #3544 is MERGED in `1af792e82935e10ae9b60a374ce5f149d2de0616`; clean main was fetched, then the T06 worktree was created from that fresh origin/main. The five plan-memory files and RESUME are now present in main.
- Current T06.2 base: branch created from fetched `origin/main` at the T06.1 merge SHA. Production checkout was not switched. Current branch still has that base HEAD; validated implementation is staged in the isolated worktree.
- Gate: initial task route misclassified runtime constructors as frontend routing. One retry with confirmed root `backend/app/services/queue_svc/_operations.py` returned `narrow_override` with only that file. The approved user plan explicitly requires a projected shared calculation and enumerates the other runtime writer modules; manual boundaries are limited to those named constructors, one new helper module, focused tests, and this plan-memory checkpoint. `gate_misroute=true`, `override_used=true`, `known_root_cause_file=backend/app/services/queue_svc/_operations.py`. No third gate attempt.
- Canonical source inventory: literal runtime constructors found in queue service, CRUD, GraphQL, queue API/limits/visit-confirmation repositories, and force-majeure service. `dev_seed.py` is a synthetic seed path. `migration_service._get_or_create_daily_queue` imports historical records and remains legacy. Its backup/restore path is an actual state-transfer writer: export currently omits the new version/count, so restoring a v1 queue would silently restore it as legacy/zero.
- First-touch scope before implementation: new `backend/app/crud/daily_queue_creation_policy.py`; `backend/app/services/queue_svc/_operations.py`; `backend/app/crud/online_queue.py`; `backend/app/graphql/mutations.py`; `backend/app/repositories/queue_api_repository.py`; `backend/app/repositories/queue_limits_repository.py`; `backend/app/repositories/visit_confirmation_repository.py`; `backend/app/services/force_majeure_service.py`; `backend/app/services/migration_service.py` restricted to backup serialization/restore; new `backend/tests/unit/test_daily_queue_creation_policy.py`; `backend/tests/unit/test_migration_service.py`; only directly necessary focused regressions; plan progress/evidence files. Denied: schema/migrations/model, `dev_seed.py`, `migration_service._get_or_create_daily_queue`, admission enforcement, cutoff, API/UI contracts, flag activation, production/staging.
- Validation target: unit tests for default-off/opt-in creation metadata and start-number inheritance; creator parity for doctor/resource identities; existing focused queue/service tests; `git diff --check`. Re-run PostgreSQL only if this patch changes schema or an actual DB-level contract.
- Completed in the current worktree: shared `daily_queue_creation_snapshot` selects legacy by default and `daily_online_issuances_v1` only for new rows when `QUEUE_POLICY_V2_CREATION_ENABLED` is truthy; active doctor/resource constructors route through it; existing rows are reused unchanged; backup/restore preserves version/count and treats old backups as legacy/0. Synthetic seed and historical import remain legacy.
- Validation: the final rerun passed 54 focused unit/integration tests (policy, backup/settings, and least-loaded routing). Earlier focused runtime-adapter runs passed 8 + 22 + 4 tests. Python compileall and `git diff --check` passed. Test DB was SQLite only. New helper/test Ruff and Black/format checks pass; import sorting passes. Ruff and non-format pre-commit hooks pass after two equivalent `dict(rows)` cleanup edits. `ruff-format` and Black pre-commit hooks were skipped on the final run because their whole-file edits would reformat unrelated legacy code; see `EVIDENCE.md#t06.2-final-validation-checkpoint`.
- Remaining: commit, push and open the T06.2 PR; recheck exact-head CI and record skipped jobs accurately. PostgreSQL/staging evidence is NOT_RUN for this patch; T06.1's disposable-PG proof remains in its own evidence. T07–T18 remain planned.
- Blocker: none currently. Stop if a writer has unclear online vs staff/import semantics or preserving its snapshot needs a product decision.
- Next exact action: commit/push this branch and open one T06.2 PR with SQLite-versus-PG/staging limitations and the skipped whole-file formatter hooks stated clearly.
- Checks to rerun after the next code change: helper and backup round-trip unit tests, changed-constructor integration tests, Ruff import check/new-file lint, compileall, and `git diff --check`. Do not run a repo-wide formatter over legacy files; it would rewrite unrelated existing sections.
- Baseline: DailyQueue is the existing `daily_queues` table, owns exactly one doctor or queue resource, and stores frozen day snapshots. Fresh main had one Alembic head, `0076_derma_history_read_order`; the active worktree now has the new single head `0077_daily_queue_policy`.
- Current patch: revision 0077 adds non-null `policy_version` (`legacy` default) and `online_issued_count` (0 default), with checks limiting policy values and rejecting negative counts. `DailyQueue` mirrors defaults and constraints. Existing queue ownership and snapshot columns are untouched. No admission writer, constructor, flag, endpoint or UI is changed.
- Required graph-test updates: six existing tests pin the current Alembic head, so those exact head assertions now advance to 0077; no historical migration behavior was changed. The queue schema contract suite adds model/revision parity and DB-default/check tests.
- PostgreSQL evidence: disposable PostgreSQL 16 completed the blank upgrade through 0076, received a synthetic resource-owned daily queue plus a synthetic `source='online'` entry at that revision, and upgraded to 0077. The same queue retained identity, resource ownership, tag, cabinet and day snapshots; policy is `legacy`, counter is `0` despite its online entry. A writer omitting both columns inserted with `legacy/0`. Invalid policy and negative counter were rejected by their named checks. A synthetic v1 row caused the downgrade guard to refuse; it was removed and the DB remained at 0077. Full details are in `EVIDENCE.md#t06.1-schema-checkpoint`.
- Validation environment: separate Compose project `aqs-t06-pg-20261001`, PostgreSQL 16, tmpfs/no volume, loopback-only port `55439`. The prior run's WSL keepalive expired and its container stopped; that proof was discarded and repeated from a clean empty container while a fresh keepalive remained active. Shared staging for PR #3524 and production were not used.
- Test fixes and current-code validation: backend CI first exposed the 0073 fixture inserting current `DailyQueue` ORM fields into a 0072 schema; commit `d3da890805fc7f1b2a7ba4a492ff80fb642a1a75` fixes that historical seeding path. Run `36867926429` then passed 5211 tests but failed the RQ17 global-empty-table assertion. Commit `b14cc03da1c0171bcfe9fe45df7035c4f93cbd9c` seeds an unrelated existing resource and verifies rejected creation leaves the baseline unchanged and does not insert `usound-r`; no runtime code changed. The focused RQ17 module passed 26 tests, 8 PostgreSQL-only cases were skipped, and hooks passed. On exact PR code HEAD `ca590e81f9afd15a9b4f04c467a4220cc9733cfb`, Unified CI run `36872005425` completed successfully: Backend, code quality, context boundary, docs generation, Frontend–Backend Parity, CI Scope, and PR Required Gate passed. CodeQL, Gitleaks, security scan, GitGuardian, PR Review Quality Gate, lifecycle recommendation, and formatting reports also passed. Path-aware Frontend unit/E2E/lint/build, DAST, Supabase Preview, staging/production readiness, load and integration jobs were skipped; skipped jobs are not passed. Synthetic staging/browser checks remain NOT_RUN.
- Remaining: finish T06.1's diff review and PR cycle. Keep T06.2 shared creation policy/constructors out of this PR; resume T06.2 only after T06.1 is merged and base/worktree are synchronized. T07–T18 remain planned.
- Blocker: none for local T06.1. Synthetic staging, production and unknown PostgreSQL services remain outside this task.
- Next exact action: confirm live PR #3545 still has the recorded passing checks and exact HEAD, then obtain the user's merge decision. Do not merge without explicit authorization, and do not begin T06.2 constructors or policy writers until merge and fresh-main synchronization.
- Checks to rerun after any code change: focused `test_queue_resource_contract.py`; the two queue migration-chain tests; `alembic heads`/`history`; disposable PG upgrade if migration/model/revision changes; pre-commit on actual changed files; `git diff --check`. T05 staging deferral is not a replacement.

## Checkpoint rules for the next agent

- Read RESUME, the canonical plan, this file, DECISIONS and current-task EVIDENCE before edits; pass the exact plan path to aif-implement.
- Preserve T00–T05 MERGED and exact merge SHAs. Never reset the registry to the initial all-PLANNED template or act on obsolete T03/T05 PR_OPEN journal entries.
- Record task/subtask, actual worktree/HEAD/diff/PR, anchors, scope, mode, validation and next action before edits and after meaningful checks.
- Keep deferrals PR-specific and distinguish accepted from passed. Record required NOT_RUN checks openly.
- Preserve unrelated local changes/scratch. Do not retry blocked deletion via an alternative method or discard the source T03 docs diff after recovering it here.
