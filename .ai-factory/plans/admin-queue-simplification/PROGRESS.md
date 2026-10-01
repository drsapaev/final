# Progress

Plan version: 1.2
Execution permission: IMPLEMENTATION_ACTIVE — user resumed the full plan on 2026-10-01
Start here: [RESUME.md](RESUME.md), then this file and current-task EVIDENCE
Canonical plan: [codex-admin-queue-simplification.md](../codex-admin-queue-simplification.md)
Current task: T06
Current status: PR_OPEN (T06.1 schema/model/test slice; regression fix committed locally, checkpoint/body update and fresh CI pending)
Last completed task: T05 — MERGED
Worktree: `C:\final\_wt_aqs_t06_policy_schema`
Branch: `codex/aqs-T06-policy-schema`
Base commit: `1af792e82935e10ae9b60a374ce5f149d2de0616`
Current commit: `d3da890805fc7f1b2a7ba4a492ff80fb642a1a75` (T06.1 historical-fixture regression fix; not pushed yet)
Last updated: 2026-10-01T18:17:46+05:00

> T00–T05 are confirmed MERGED. T06.1 PR #3545 is open; T06.2 and T07–T18 remain PLANNED. The #3543 staging deferral remains separate and staging stays NOT_RUN. No production activation is authorized.

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00 | MERGED | `codex/aqs-T00-docs` / [PR #3536](https://github.com/drsapaev/final/pull/3536) | `bae927f5c88010808d9091e7f47d09bbfdfa1005` | `EVIDENCE.md#t00` |
| T01 | MERGED | `codex/aqs-T01-profile-modal` / [PR #3537](https://github.com/drsapaev/final/pull/3537) | `967bd398c14bce4b835bd5be1205532387e2a909` | `EVIDENCE.md#t01` |
| T02 | MERGED | `codex/aqs-T02-queue-settings-state` / [PR #3538](https://github.com/drsapaev/final/pull/3538) | `b4ba6320797f056da19bbdc5cc672b3a97d2091e` | `EVIDENCE.md#t02` |
| T03 | MERGED | `codex/aqs-T03-cabinet-read` / [PR #3540](https://github.com/drsapaev/final/pull/3540) | `1e781da72bd927926b538b139a6c251cd09848b5` | `EVIDENCE.md#t03-merge-checkpoint` |
| T04 | MERGED | `codex/aqs-T04-empty-profiles` / [PR #3541](https://github.com/drsapaev/final/pull/3541) | `ecc14b05411c7e7b54efca2966416cd6a69df37c` | `EVIDENCE.md#t04-merge-checkpoint` |
| T05 | MERGED | `codex/aqs-T05-settings-cache` / [PR #3543](https://github.com/drsapaev/final/pull/3543) | `fd53206f03b0361de6fc345f53b2bacf4195845c` | `EVIDENCE.md#t05-merge-checkpoint` |
| T06 | PR_OPEN | `codex/aqs-T06-policy-schema` / [PR #3545](https://github.com/drsapaev/final/pull/3545), T06.1 | | `EVIDENCE.md#t06.1-schema-checkpoint`; `EVIDENCE.md#t06.1-pr-open` |
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

- Completed: T00–T05 MERGED. T03 includes the omitted-day Sync clinic/host-date regression fix; T04 removes empty/error profile fallbacks; T05 refreshes defaults per top-level command while nested methods share a task-local settings mapping. Existing daily time/number snapshots stay fixed.
- T05 review/merge: exact reviewed head `c04f41021bef5f8c306b9668cbb1c4b9afef2cc1`; runtime source unchanged since `47276d178972226b0bcf561bdf8fa26a6940b913`; merge `fd53206f03b0361de6fc345f53b2bacf4195845c` at 2026-10-01T16:24:40+05:00. Reviewed and merged trees match. Applicable backend/quality/contract/security gates passed; skipped path-aware jobs are not passed. No GitHub author-approval review was fabricated.
- Deferral: accepted for #3543/T05 by agent decision under the user's explicit delegation. Full requirement/reason/evidence/owner/resume/headline fields are in DECISIONS and `EVIDENCE.md#t05-merge-checkpoint`. Local PG integration, synthetic staging/admin/queue E2E and cold/repeat timing remain NOT_RUN. The executing AQS agent owns resumption at T18/pre-deploy; T06's mandatory disposable-PG upgrade is not waived.
- Validation after merge: six focused queue unit files passed on `fd53206f` — 24 passed, 1 warning, Python 3.11.9 and isolated SQLite fixture. This is not PostgreSQL/staging proof. Earlier source lint/compile/hook results and baseline formatting limitations remain in timestamped T05 evidence.
- Base/cleanup: production checkout was clean `main` and fast-forwarded to `fd53206f`. No production process restarted, data queried, feature flag toggled or deployment settings changed. T05 runtime branch removed locally/remotely; detached worktree retained with untracked scratch. Earlier T03 local documents/scratch remain untouched.
- Documentation checkpoint #3544 is MERGED in `1af792e82935e10ae9b60a374ce5f149d2de0616`; clean main was fetched, then the T06 worktree was created from that fresh origin/main. The five plan-memory files and RESUME are now present in main.
- Gate: first result routed to runtime packaging; one `--known-root-cause backend/app/models/online_queue.py` retry correctly classified a migration but limited first-touch to `backend/alembic/versions/0077_*.py`, with the model read-only. The manual override is limited to the new revision, matching model fields/constraints, focused schema tests, current-head assertion maintenance, and this plan's checkpoint. The Alembic revision was the first source edit. Do not extend override to T06.2 constructors, admission policy or feature flags.
- Baseline: DailyQueue is the existing `daily_queues` table, owns exactly one doctor or queue resource, and stores frozen day snapshots. Fresh main had one Alembic head, `0076_derma_history_read_order`; the active worktree now has the new single head `0077_daily_queue_policy`.
- Current patch: revision 0077 adds non-null `policy_version` (`legacy` default) and `online_issued_count` (0 default), with checks limiting policy values and rejecting negative counts. `DailyQueue` mirrors defaults and constraints. Existing queue ownership and snapshot columns are untouched. No admission writer, constructor, flag, endpoint or UI is changed.
- Required graph-test updates: six existing tests pin the current Alembic head, so those exact head assertions now advance to 0077; no historical migration behavior was changed. The queue schema contract suite adds model/revision parity and DB-default/check tests.
- PostgreSQL evidence: disposable PostgreSQL 16 completed the blank upgrade through 0076, received a synthetic resource-owned daily queue plus a synthetic `source='online'` entry at that revision, and upgraded to 0077. The same queue retained identity, resource ownership, tag, cabinet and day snapshots; policy is `legacy`, counter is `0` despite its online entry. A writer omitting both columns inserted with `legacy/0`. Invalid policy and negative counter were rejected by their named checks. A synthetic v1 row caused the downgrade guard to refuse; it was removed and the DB remained at 0077. Full details are in `EVIDENCE.md#t06.1-schema-checkpoint`.
- Validation environment: separate Compose project `aqs-t06-pg-20261001`, PostgreSQL 16, tmpfs/no volume, loopback-only port `55439`. The prior run's WSL keepalive expired and its container stopped; that proof was discarded and repeated from a clean empty container while a fresh keepalive remained active. Shared staging for PR #3524 and production were not used.
- Changed but not fully verified: backend CI for the original PR head exposed a historical-fixture incompatibility: `test_nurse_serving_0073_backfill_pg.py` seeded queues with the current ORM after migrating its disposable database only to 0072. Commit `d3da890805fc7f1b2a7ba4a492ff80fb642a1a75` now inserts those pre-0073 rows with the 0072 column shape. On isolated local PostgreSQL 16, the regression module passed 5 tests and the combined regression/schema-contract selection passed 29 tests (1 warning); targeted Ruff, Ruff format, Black, commit hooks and diff checks passed. The correction is committed locally but not pushed. PR #3545 remains open; final checks must run on the pushed new HEAD. Earlier PR checks are not final evidence. Path-aware frontend jobs are skipped, not passed. T05 staging coverage remains NOT_RUN and is not waived by this local PG evidence.
- Remaining: finish T06.1's diff review and PR cycle. Keep T06.2 shared creation policy/constructors out of this PR; resume T06.2 only after T06.1 is merged and base/worktree are synchronized. T07–T18 remain planned.
- Blocker: none for local T06.1. Synthetic staging, production and unknown PostgreSQL services remain outside this task.
- Next exact action: finish this checkpoint with commit `d3da890805fc7f1b2a7ba4a492ff80fb642a1a75`, update the PR body with the regression and local PG results, run the PR body gate, push the existing branch, then wait for applicable checks on that exact HEAD. Fix any red check in the same PR. After current-head checks finish, present the concrete merge decision; do not begin T06.2 until T06.1 is merged and the worktree is synced.
- Checks to rerun after any code change: focused `test_queue_resource_contract.py`; the two queue migration-chain tests; `alembic heads`/`history`; disposable PG upgrade if migration/model/revision changes; pre-commit on actual changed files; `git diff --check`. T05 staging deferral is not a replacement.

## Checkpoint rules for the next agent

- Read RESUME, the canonical plan, this file, DECISIONS and current-task EVIDENCE before edits; pass the exact plan path to aif-implement.
- Preserve T00–T05 MERGED and exact merge SHAs. Never reset the registry to the initial all-PLANNED template or act on obsolete T03/T05 PR_OPEN journal entries.
- Record task/subtask, actual worktree/HEAD/diff/PR, anchors, scope, mode, validation and next action before edits and after meaningful checks.
- Keep deferrals PR-specific and distinguish accepted from passed. Record required NOT_RUN checks openly.
- Preserve unrelated local changes/scratch. Do not retry blocked deletion via an alternative method or discard the source T03 docs diff after recovering it here.
