# Progress

Plan version: 1.2
Execution permission: IMPLEMENTATION_ACTIVE — user resumed the full plan on 2026-10-01
Start here: [RESUME.md](RESUME.md), then this file and current-task EVIDENCE
Canonical plan: [codex-admin-queue-simplification.md](../codex-admin-queue-simplification.md)
Current task: T06
Current status: PR_OPEN (T06.1; backend regression fix b14 committed locally; PR HEAD 529 failed one unrelated test assertion, follow-up CI pending)
Last completed task: T05 — MERGED
Worktree: `C:\final\_wt_aqs_t06_policy_schema`
Branch: `codex/aqs-T06-policy-schema`
Base commit: `1af792e82935e10ae9b60a374ce5f149d2de0616`
Current commit: `b14cc03da1c0171bcfe9fe45df7035c4f93cbd9c` (test-only RQ17 assertion fix; local, not pushed)
Last updated: 2026-10-01T18:48:42+05:00

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
- Changed but not fully verified: first, backend CI exposed the 0073 fixture inserting current `DailyQueue` ORM fields into a 0072 schema; commit `d3da890805fc7f1b2a7ba4a492ff80fb642a1a75` fixes that historical seeding path. The next full run on PR HEAD `529644a94000c5adc50ef740c167fa970466ac2e` passed 5211 tests but failed `test_pin1_post_active_resource_on_requires_doctor_tag_rejected`, whose absolute expectation that the shared test table was empty was invalid in the full-suite context. Commit `b14cc03da1c0171bcfe9fe45df7035c4f93cbd9c` seeds an unrelated existing resource and checks that rejected creation leaves the count unchanged and does not insert `usound-r`; no runtime code changed. The focused RQ17 module passed 26 tests, 8 PostgreSQL-only cases were skipped, and hooks passed. The new fix is local and not pushed; PR #3545 still has a red Backend/Required Gate at 529 and requires a fresh CI run. Code Quality, Context Boundary, docs, security, gitleaks, CodeQL and lifecycle passed at 529. Parity was skipped because the backend failure prevented its dependent job from running, and Required Gate reported it as skipped. Path-aware frontend jobs are skipped, not passed. T05 staging coverage remains NOT_RUN and is not waived by local tests.
- Remaining: finish T06.1's diff review and PR cycle. Keep T06.2 shared creation policy/constructors out of this PR; resume T06.2 only after T06.1 is merged and base/worktree are synchronized. T07–T18 remain planned.
- Blocker: none for local T06.1. Synthetic staging, production and unknown PostgreSQL services remain outside this task.
- Next exact action: commit the T06.1 checkpoint/body update, push local commit `b14cc03da1c0171bcfe9fe45df7035c4f93cbd9c` to the existing branch, then wait for all applicable checks on the new PR HEAD. Confirm parity runs after backend passes. Fix any remaining red check in this PR; do not begin T06.2 before merge and fresh-main sync.
- Checks to rerun after any code change: focused `test_queue_resource_contract.py`; the two queue migration-chain tests; `alembic heads`/`history`; disposable PG upgrade if migration/model/revision changes; pre-commit on actual changed files; `git diff --check`. T05 staging deferral is not a replacement.

## Checkpoint rules for the next agent

- Read RESUME, the canonical plan, this file, DECISIONS and current-task EVIDENCE before edits; pass the exact plan path to aif-implement.
- Preserve T00–T05 MERGED and exact merge SHAs. Never reset the registry to the initial all-PLANNED template or act on obsolete T03/T05 PR_OPEN journal entries.
- Record task/subtask, actual worktree/HEAD/diff/PR, anchors, scope, mode, validation and next action before edits and after meaningful checks.
- Keep deferrals PR-specific and distinguish accepted from passed. Record required NOT_RUN checks openly.
- Preserve unrelated local changes/scratch. Do not retry blocked deletion via an alternative method or discard the source T03 docs diff after recovering it here.
