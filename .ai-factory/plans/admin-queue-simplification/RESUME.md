# Resume — admin queue simplification

Plan version: 1.7
Last updated: 2026-10-01T22:30:40+05:00, Asia/Tashkent
Execution permission: IMPLEMENTATION_ACTIVE; user instructed “мержай и продолжай” for the active PR cycle; T06.2 has been rebased a second time and needs exact-head CI

## First read

1. Repo `AGENTS.md`, `docs/runbooks/AGENT_CYCLIC_WORKFLOW.md` and `docs/runbooks/AGENT_SESSION_WORKTREES.md`.
2. [Canonical detailed plan](../codex-admin-queue-simplification.md).
3. [PROGRESS.md](PROGRESS.md), [DECISIONS.md](DECISIONS.md), then current-task [EVIDENCE.md](EVIDENCE.md).
4. Before ownership/schema work: `docs/devbrain/PROJECT_MEMORY.md`, `DEVBRAIN_STATUS.md`, `MEMORY_ROUTING.md`, `DEV_BRAIN_ROLE_MAP.md`, the direction contract and ADR-001.

The user resumed implementation with “Продолжай реализации плана”. The later request delegated the staging/merge decision for #3543. It did not waive future schema/admission gates or authorize production activation.

## Verified checkpoint

- T00–T05 and T06.1 are MERGED. [PR #3545](https://github.com/drsapaev/final/pull/3545) merged at `e8f585ab0a51e256fa638fe56c0582eff0bbafc6` after explicit user authorization. Its schema adds legacy-safe policy version/counter fields; it does not update constructors or enable v1 creation. T06.2 is now active; do not repeat T06.1.
- T05 [PR #3543](https://github.com/drsapaev/final/pull/3543) merged at `fd53206f03b0361de6fc345f53b2bacf4195845c`, 2026-10-01T16:24:40+05:00, from reviewed head `c04f41021bef5f8c306b9668cbb1c4b9afef2cc1`. Runtime code dates from `47276d178972226b0bcf561bdf8fa26a6940b913`; merged/reviewed trees match.
- Applicable T05 CI gates passed. Merged-tree focused tests: 24 passed, 1 warning. Local PostgreSQL integration, synthetic staging/browser E2E and cold/repeat timing are NOT_RUN. Skipped jobs are not PASS.
- The executing agent accepted a bounded #3543/T05 deferral under the user's explicit delegation. Original requirement, reason, evidence, owner, resume condition and headline impact are in DECISIONS/EVIDENCE. No GitHub author-approval review was invented. Prior PR acknowledgments were not inherited.
- T03 already fixed omitted-day cabinet Sync to `clinic_today(db)` after the user's P1 review. Do not reopen that closed defect from obsolete planning text.
- Documentation closure [PR #3544](https://github.com/drsapaev/final/pull/3544) is merged at base `1af792e82935e10ae9b60a374ce5f149d2de0616`; its five plan-memory files are available in the active worktree.

Check actual git status/HEAD and GitHub PR state first. If they differ from this record, restore the factual checkpoint before editing. Timestamped EVIDENCE entries with PR_OPEN are historical, not current instructions.

## Active runtime step — T06.2

- Worktree: `C:\final\_wt_aqs_t062_creation_policy`; branch `codex/aqs-T06.2-creation-policy`; latest base `origin/main` `1358c70bf4723d151861a9ef135bba147b118fee` after clean second rebase. The new base only adds a mutation-test deselection in `backend/pyproject.toml`. Post-rebase focused tests passed 54/54 and `git diff --check` passed. PR #3546 still needs force-with-lease push and fresh checks; verify the live head before merge.
- Gate: initial routing misclassified queue-constructor work as frontend route ownership. The sole retry with known root `backend/app/services/queue_svc/_operations.py` returned a one-file override. The explicit user-approved T06.2 plan authorizes the projected shared helper plus the listed runtime constructors and focused tests; manual override is restricted to the exact allowlist in PROGRESS. Record the gate misroute/override in EVIDENCE; do not retry the gate.
- Runtime scope: new shared calculation, `queue_svc/_operations.py`, `crud/online_queue.py`, `graphql/mutations.py`, queue API/limits/visit-confirmation repositories, and force-majeure queue creation. `dev_seed.py` remains synthetic legacy seed; `migration_service._get_or_create_daily_queue` remains historical import. The backup serializer/restore in `migration_service.py` is in scope only to preserve `policy_version`/`online_issued_count` and default old backups to legacy/0; source inspection proved omission would reset a restored v1 counter. No schema/migration changes, cutoff/quota enforcement, ordinary API/UI, flag activation, staging or production.
- Implemented: shared `daily_queue_creation_snapshot`; queue-service, legacy CRUD, GraphQL, queue API/limits/visit-confirmation repositories and force-majeure constructors use it. V1 selection remains default-off. Backup/restore carries policy/count, while old backups restore to legacy/0. Synthetic seed and historical import stay legacy.
- Local checks: final rerun — 54 policy/backup/settings and least-loaded routing unit/integration tests passed; earlier constructor-adapter runs passed 8 + 22 + 4 tests. The CRUD regression preserves explicit legacy `start_number`. `compileall`, `git diff --check`, helper/test Ruff+Black, import sorting and Ruff pre-commit passed. The final pre-commit run passed all non-format hooks; `ruff-format` and Black were skipped because whole-file formatting rewrote unrelated legacy code. Two equivalent `dict(rows)` cleanup edits removed pre-existing Ruff C416 failures. SQLite only; no T06.2 PostgreSQL or staging check. See `EVIDENCE.md#t06.2-final-validation-checkpoint`.
- Current exact next action: push the second rebased T06.2 branch and wait for all applicable required checks on that exact head. PR #3546 is already ready. The user instructed “мержай и продолжай”; if exact-head checks pass and merge state is clean, merge promptly, then sync `origin/main` before T07. Synthetic staging/browser remains NOT_RUN; do not activate the feature flag or deploy.

The T05 deferral does not waive T06.2 validation. Close the T06.2 PR cycle before T07; do not begin T07 while T06 is unresolved.

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
