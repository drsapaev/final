# Progress

Plan version: 2.3
Execution permission: IMPLEMENTATION_ACTIVE — user resumed the full plan on 2026-10-01
Start here: [RESUME.md](RESUME.md), then this file and current-task EVIDENCE
Canonical plan: [codex-admin-queue-simplification.md](../codex-admin-queue-simplification.md)
Current task: T08.1a — canonical token admission quota
Current status: T07 MERGED. PR #3557 merged as 425df11c7a84f0d1e7954df0d00415927212669a; final CI 27 SUCCESS / 12 SKIPPED / 0 failures. T08.1a is PR_OPEN on PR #3571, current PR HEAD d13505357ac7701345b14896f6b1f7b4c0b22cbe, base 473138216ae040c1c7fa60e92334d33ef8a0b856. The corrected PR body passes local validation and the latest GitHub PR Review Quality Gate; exact-head Unified CI is in progress. No Tier-2 staging deferral is claimed for this backend-only slice. Later T08 writers and PostgreSQL proof remain open; v1 flag stays default-off.
Last completed task: T07 — MERGED (#3557, merge commit 425df11c7a84f0d1e7954df0d00415927212669a)
Worktree: C:\final\_wt_aqs_t081_quota
Branch: codex/aqs-T081-online-quota
Base commit: 473138216ae040c1c7fa60e92334d33ef8a0b856
Last runtime/test commit: e0ebcfb756cf1ff31093c5905aed9b937a2fa769 (T08.1a, local branch); base 473138216ae040c1c7fa60e92334d33ef8a0b856.
Last updated: 2026-10-03T19:33:00+05:00

> Historical checkpoint superseded: current T07 status and exact-head evidence are recorded in dated sections below and in RESUME.md; do not use the earlier snapshot as a continuation instruction.

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00 | MERGED | `codex/aqs-T00-docs` / [PR #3536](https://github.com/drsapaev/final/pull/3536) | `bae927f5c88010808d9091e7f47d09bbfdfa1005` | `EVIDENCE.md#t00` |
| T01 | MERGED | `codex/aqs-T01-profile-modal` / [PR #3537](https://github.com/drsapaev/final/pull/3537) | `967bd398c14bce4b835bd5be1205532387e2a909` | `EVIDENCE.md#t01` |
| T02 | MERGED | `codex/aqs-T02-queue-settings-state` / [PR #3538](https://github.com/drsapaev/final/pull/3538) | `b4ba6320797f056da19bbdc5cc672b3a97d2091e` | `EVIDENCE.md#t02` |
| T03 | MERGED | `codex/aqs-T03-cabinet-read` / [PR #3540](https://github.com/drsapaev/final/pull/3540) | `1e781da72bd927926b538b139a6c251cd09848b5` | `EVIDENCE.md#t03-merge-checkpoint` |
| T04 | MERGED | `codex/aqs-T04-empty-profiles` / [PR #3541](https://github.com/drsapaev/final/pull/3541) | `ecc14b05411c7e7b54efca2966416cd6a69df37c` | `EVIDENCE.md#t04-merge-checkpoint` |
| T05 | MERGED | `codex/aqs-T05-settings-cache` / [PR #3543](https://github.com/drsapaev/final/pull/3543) | `fd53206f03b0361de6fc345f53b2bacf4195845c` | `EVIDENCE.md#t05-merge-checkpoint` |
| T06.1 | MERGED | `codex/aqs-T06-policy-schema` / [PR #3545](https://github.com/drsapaev/final/pull/3545) | `e8f585ab0a51e256fa638fe56c0582eff0bbafc6` | `EVIDENCE.md#t06.1-merge-checkpoint` |
| T06.2 | MERGED | `codex/aqs-T06.2-creation-policy` / [PR #3546](https://github.com/drsapaev/final/pull/3546) | `b804a71a6bad22400324e2236a3221317eac3158` | `EVIDENCE.md#t06.2-merge-checkpoint` |
| T07 | MERGED | codex/aqs-T07-admission-window / PR #3557 | 425df11c7a84f0d1e7954df0d00415927212669a | EVIDENCE.md#t07-merge-and-t08-gate-source-audit |
| T08 | IN_PROGRESS | codex/aqs-T081-online-quota / PR #3571 (T08.1a PR_OPEN) | | EVIDENCE.md#t08-token-admission-quota-scope |
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

- T07/PR #3557 is MERGED as 425df11c7a84f0d1e7954df0d00415927212669a; exact-head applicable CI finished 27 SUCCESS / 12 SKIPPED / 0 failures. Its three named Tier-2 deferrals remain NOT_RUN; full STAGING_VALIDATION remains mandatory before deployment.
- T08.1a implementation is committed as e0ebcfb756cf1ff31093c5905aed9b937a2fa769 on base 473138216ae040c1c7fa60e92334d33ef8a0b856; current docs/PR checkpoint is d13505357ac7701345b14896f6b1f7b4c0b22cbe. It uses online_issued_count for v1 admission and doctor selection; increments only after new entry creation under the locked queue row, before the existing commit/flush. Legacy active-entry behavior is unchanged. No other admission writer, constructor, report, flag, or schema was changed.
- Validation: focused queue-claim, admission-window, and QR least-loaded routing suites 64 passed / 1 warning on test-fixture SQLite; scoped Ruff check, compile, and git diff --check PASS. The test file passes Ruff format check. Ruff format check for the legacy _operations.py reports broad existing changes outside this patch; no whole-file reformat was applied. PostgreSQL concurrency, GraphQL/direct writers, queue identity recreation and staging are NOT_RUN/reserved for later T08 slices.
- PR #3571: body template gate initially failed because the first description lacked required sections. The body is now corrected; local validator passed (19 tests, sample bodies and actual PR body), and GitHub PR Review Quality Gate run 37129646426 passed on HEAD d13505357ac7701345b14896f6b1f7b4c0b22cbe. A rerun of the original event still failed on its stale body snapshot; it is historical and superseded by the fresh edited-event pass.
- Exact-head Unified CI run 37129318025 is in progress on d13505357. Backend tests, Code Quality and Context Boundary jobs are running; frontend-only jobs and path-specific checks are skipped. No separate human review verdict is recorded. Keep QUEUE_POLICY_V2_CREATION_ENABLED unset/default-off.
- Blocker: final exact-head CI is still in progress. PostgreSQL concurrency proof remains NOT_RUN and is required in T08.3 before rollout, but does not change this backend-only PR's scope.
- Next exact action: wait for run 37129318025 to complete; record its passed/failed/skipped jobs and confirm the PR still points at the tested head before completing this PR cycle. Do not start the next subtask before the PR cycle is complete.
- Checks to rerun after the next runtime change: the two focused modules, scoped Ruff check, compile, and git diff --check. PostgreSQL concurrency proof remains a T08.3 gate and must be completed before v1 rollout/flag activation.
## Checkpoint rules for the next agent

- Read RESUME, the canonical plan, this file, DECISIONS and current-task EVIDENCE before edits; pass the exact plan path to aif-implement.
- Preserve T00–T05 MERGED and exact merge SHAs. Never reset the registry to the initial all-PLANNED template or act on obsolete T03/T05 PR_OPEN journal entries.
- Record task/subtask, actual worktree/HEAD/diff/PR, anchors, scope, mode, validation and next action before edits and after meaningful checks.
- Keep deferrals PR-specific and distinguish accepted from passed. Record required NOT_RUN checks openly.
- Preserve unrelated local changes/scratch. Do not retry blocked deletion via an alternative method or discard the source T03 docs diff after recovering it here.

- Latest review/fix checkpoint (2026-10-03): deterministic baseline reproduction confirmed a new token entry could be created at 09:00:01 after passing the 09:00 gate at 08:59:59 and waiting for the numbering row lock. Fix commit `4595d67a6e484bab8a9a59277bdaf2775e143d56` locks and refreshes the queue before the gate. Regression now rejects both tagged and untagged queues without entry or usage increment. See `EVIDENCE.md#t07-token-cutoff-lock-review-fix`.
- Next exact action: update PR body with this Admin staging result and exact-head CI, commit and push the evidence checkpoint, then inspect checks for the actual pushed HEAD. Keep merge on hold pending independent human review and remaining Tier 2 or an explicit #3557-specific deferral. Do not begin T08.
