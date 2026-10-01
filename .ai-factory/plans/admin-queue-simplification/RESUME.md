# Resume — admin queue simplification

Plan version: 1.2
Last updated: 2026-10-01, Asia/Tashkent
Execution permission: IMPLEMENTATION_ACTIVE; current closure is documentation only

## First read

1. Repo `AGENTS.md`, `docs/runbooks/AGENT_CYCLIC_WORKFLOW.md` and `docs/runbooks/AGENT_SESSION_WORKTREES.md`.
2. [Canonical detailed plan](../codex-admin-queue-simplification.md).
3. [PROGRESS.md](PROGRESS.md), [DECISIONS.md](DECISIONS.md), then current-task [EVIDENCE.md](EVIDENCE.md).
4. Before ownership/schema work: `docs/devbrain/PROJECT_MEMORY.md`, `DEVBRAIN_STATUS.md`, `MEMORY_ROUTING.md`, `DEV_BRAIN_ROLE_MAP.md`, the direction contract and ADR-001.

The user resumed implementation with “Продолжай реализации плана”. The later request delegated the staging/merge decision for #3543. It did not waive future schema/admission gates or authorize production activation.

## Verified checkpoint

- T00–T05 are MERGED. T06–T18 are PLANNED. No T06 migration or runtime edit exists in this checkpoint.
- T05 [PR #3543](https://github.com/drsapaev/final/pull/3543) merged at `fd53206f03b0361de6fc345f53b2bacf4195845c`, 2026-10-01T16:24:40+05:00, from reviewed head `c04f41021bef5f8c306b9668cbb1c4b9afef2cc1`. Runtime code dates from `47276d178972226b0bcf561bdf8fa26a6940b913`; merged/reviewed trees match.
- Applicable T05 CI gates passed. Merged-tree focused tests: 24 passed, 1 warning. Local PostgreSQL integration, synthetic staging/browser E2E and cold/repeat timing are NOT_RUN. Skipped jobs are not PASS.
- The executing agent accepted a bounded #3543/T05 deferral under the user's explicit delegation. Original requirement, reason, evidence, owner, resume condition and headline impact are in DECISIONS/EVIDENCE. No GitHub author-approval review was invented. Prior PR acknowledgments were not inherited.
- T03 already fixed omitted-day cabinet Sync to `clinic_today(db)` after the user's P1 review. Do not reopen that closed defect from obsolete planning text.
- Documentation closure: [PR #3544](https://github.com/drsapaev/final/pull/3544), branch `codex/aqs-T05-closure`, worktree `C:\final\_wt_aqs_t05_closure`, base `fd53206f`. Verify its live merge/current-head checks before the next runtime cycle. Closure commits change the five plan-memory files only.

Check actual git status/HEAD and GitHub PR state first. If they differ from this record, restore the factual checkpoint before editing. Timestamped EVIDENCE entries with PR_OPEN are historical, not current instructions.

## Next exact runtime step — T06

1. Fetch fresh `origin/main`; confirm T05 and documentation closure are merged. Keep `C:\final` on clean main; never switch/rebase it. Create an owned worktree and `codex/aqs-T06-<topic>` branch from fresh main.
2. Use aif-implement with the explicit absolute plan path in that worktree: `$aif-implement @C:/final/<owned-T06-worktree>/.ai-factory/plans/codex-admin-queue-simplification.md`. Replace the placeholder with the actual path. Do not duplicate the plan under a branch-derived filename.
3. Ground the T06 card on current source: `backend/app/models/online_queue.py:DailyQueue`, creation paths, resource/start-number policy, identity constraints, migration heads/history. Historical anchors are references, not an edit allowlist.
4. Enumerate active constructors and compatibility/offline paths; record transaction owners and unresolved identity writers. Propose the smallest T06.1 model/new-revision legacy-safe slice before T06.2 shared creation calculation.
5. Record execution mode, canonical/reference-only/first-touch/denied paths, baseline, checks and stop conditions in PROGRESS/EVIDENCE before the first edit. DB/Alembic requires `gate` or `gate_known_root_cause`; run the verified `ai/langgraph/scripts/run_agent_gate.ps1` from the T06 worktree and read its mandatory execution boundary.
6. Establish an isolated disposable PostgreSQL environment and prove heads/history, non-destructive upgrade, legacy data/ownership/constraints and CHECK behavior. SQLite or T05 backend CI does not replace this migration proof. Stop dependent work and record BLOCKED if required gate/PG or constructor ownership cannot be established.
7. Keep `QUEUE_POLICY_V2_CREATION_ENABLED` default false. Do not enable v1, convert legacy/future queues, change issued numbers/history/queue_time, or deploy as part of T06.

The T05 deferral does not authorize bypassing any T06 requirement. Close each small PR cycle before the next one; do not begin T07 while T06 is unresolved.

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
