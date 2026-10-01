# Resume — admin queue simplification

Plan version: 1.2
Last updated: 2026-10-01, Asia/Tashkent
Execution permission: IMPLEMENTATION_ACTIVE; T06.1 PR #3545 is open, CI in progress

## First read

1. Repo `AGENTS.md`, `docs/runbooks/AGENT_CYCLIC_WORKFLOW.md` and `docs/runbooks/AGENT_SESSION_WORKTREES.md`.
2. [Canonical detailed plan](../codex-admin-queue-simplification.md).
3. [PROGRESS.md](PROGRESS.md), [DECISIONS.md](DECISIONS.md), then current-task [EVIDENCE.md](EVIDENCE.md).
4. Before ownership/schema work: `docs/devbrain/PROJECT_MEMORY.md`, `DEVBRAIN_STATUS.md`, `MEMORY_ROUTING.md`, `DEV_BRAIN_ROLE_MAP.md`, the direction contract and ADR-001.

The user resumed implementation with “Продолжай реализации плана”. The later request delegated the staging/merge decision for #3543. It did not waive future schema/admission gates or authorize production activation.

## Verified checkpoint

- T00–T05 are MERGED. T06.1 is open as [PR #3545](https://github.com/drsapaev/final/pull/3545). Backend CI found a historical-fixture failure at 0072; correction commit `d3da890805fc7f1b2a7ba4a492ff80fb642a1a75` seeds the old queue shape through SQL and is locally validated against isolated PostgreSQL 16 (5 regression tests and 29 combined tests passed). The code commit awaits push and fresh CI. T06.2 and T07–T18 remain PLANNED.
- T05 [PR #3543](https://github.com/drsapaev/final/pull/3543) merged at `fd53206f03b0361de6fc345f53b2bacf4195845c`, 2026-10-01T16:24:40+05:00, from reviewed head `c04f41021bef5f8c306b9668cbb1c4b9afef2cc1`. Runtime code dates from `47276d178972226b0bcf561bdf8fa26a6940b913`; merged/reviewed trees match.
- Applicable T05 CI gates passed. Merged-tree focused tests: 24 passed, 1 warning. Local PostgreSQL integration, synthetic staging/browser E2E and cold/repeat timing are NOT_RUN. Skipped jobs are not PASS.
- The executing agent accepted a bounded #3543/T05 deferral under the user's explicit delegation. Original requirement, reason, evidence, owner, resume condition and headline impact are in DECISIONS/EVIDENCE. No GitHub author-approval review was invented. Prior PR acknowledgments were not inherited.
- T03 already fixed omitted-day cabinet Sync to `clinic_today(db)` after the user's P1 review. Do not reopen that closed defect from obsolete planning text.
- Documentation closure [PR #3544](https://github.com/drsapaev/final/pull/3544) is merged at base `1af792e82935e10ae9b60a374ce5f149d2de0616`; its five plan-memory files are available in the active worktree.

Check actual git status/HEAD and GitHub PR state first. If they differ from this record, restore the factual checkpoint before editing. Timestamped EVIDENCE entries with PR_OPEN are historical, not current instructions.

## Active runtime step — T06.1

- Worktree: `C:\final\_wt_aqs_t06_policy_schema`; branch `codex/aqs-T06-policy-schema`; base `1af792e82935e10ae9b60a374ce5f149d2de0616`; code commit `e3c7d5f2dea3a9aab40d650490431a87b84e9372`.
- Changed: new revision `backend/alembic/versions/0077_daily_queue_policy.py`; `DailyQueue` fields/defaults/checks; focused schema/migration-parity tests; six exact current-head expectation updates; PROGRESS/EVIDENCE/RESUME.
- Validation: `alembic heads` returns only `0077_daily_queue_policy`; `alembic history` exits 0. Disposable PostgreSQL 16 upgrade/data-preservation/default/check/downgrade-guard evidence is recorded in `EVIDENCE.md#t06.1-schema-checkpoint`. After backend CI found the 0072 historical fixture using current `DailyQueue` ORM columns, that fixture now seeds the old queue shape with raw SQL; `test_nurse_serving_0073_backfill_pg.py` and `test_queue_resource_contract.py` passed together (29 passed, 1 warning) on isolated PostgreSQL 16. Targeted Ruff/format/Black and `git diff --check` passed. Final CI must be checked on the follow-up commit.
- Do not commit `.t06-pg.compose.yml`; it is local disposable infrastructure scratch. Do not run or stop the separate PR #3524 staging Compose project. No production DB/process/configuration or flag was touched.
- Next exact action: commit the plan checkpoint referencing `d3da890805fc7f1b2a7ba4a492ff80fb642a1a75`, update PR #3545's body, push the existing branch, and wait for applicable CI on the new HEAD. Fix any red check in the same PR. After current-head checks finish, request the merge decision. Do not begin T06.2 constructors or policy writers until this PR is merged and the worktree is synced to fresh main.

The T05 deferral does not authorize bypassing any T06 requirement. Close each small PR cycle before the next one; do not begin T07 while T06 is unresolved. T06.2 is a required separate continuation after T06.1, not a reason to widen this schema PR.

## Deferred staging coverage

- Owner: executing AQS agent, tracked through T18 and pre-deploy validation.
- Resume when isolated synthetic staging and QA access are available: T05 admin-save/new-command/existing-snapshot smoke; affected queue/admin backend-dependent E2E; cold/repeat actual-content timing; relevant local PG integration on disposable PG.
- Revalidate against the actual candidate deployment commit and record every PASS/FAIL/NOT_RUN. Deferral is accepted, not a passed scenario.
- Before production rollout run the full `docs/runbooks/STAGING_VALIDATION.md`, with all ten checks individually evidenced. No production restart, feature-flag activation or data change was performed in this closure.

## Local worktree preservation

- The detailed 1.1 plan and decisions were recovered from `C:\final\_wt_aqs_t03_cabinet_read`; its original tracked/untracked changes remain untouched. Version 1.2 publishes the recovered detail plus current facts.
- `C:\final\_wt_aqs_t05_settings_cache` is detached at the T05 merge; its local/remote runtime branch was removed. Untracked PR-body files and temporary pre-commit environment are retained.
- An earlier automatic approval review rejected scratch deletion. Do not bypass it with another deletion technique or discard unrelated local edits. Scratch is not part of the PR.

Before compaction, handoff or session end update the actual task/HEAD/diff/checks/next action in PROGRESS and append evidence. Do not rely on chat history alone.
