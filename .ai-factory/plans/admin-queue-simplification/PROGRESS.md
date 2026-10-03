# Progress

Plan version: 2.4
Execution permission: IMPLEMENTATION_ACTIVE — user resumed the full plan on 2026-10-01
Start here: [RESUME.md](RESUME.md), then this file and current-task EVIDENCE
Canonical plan: [codex-admin-queue-simplification.md](../codex-admin-queue-simplification.md)
Current task: T08.1b — v1 identity/recreation guard
Current status: T07/#3557 and T08.1a/#3571 are MERGED. #3571 merge commit and current base: d397656c7f597d72d6a6c92676cd204aff72d4d8. T08.1b source changes are validated locally in an isolated worktree; PR not opened yet. No PostgreSQL concurrency or staging claim. V1 flag stays default-off.
Last completed task: T08.1a — MERGED (#3571, merge commit d397656c7f597d72d6a6c92676cd204aff72d4d8)
Worktree: C:\final\_wt_aqs_t081b_identity
Branch: codex/aqs-T081b-identity-guard
Base commit: d397656c7f597d72d6a6c92676cd204aff72d4d8
Current code commit: none yet; working diff is uncommitted.
Last updated: 2026-10-03T20:43:00+05:00

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
| T08 | IN_PROGRESS | codex/aqs-T081b-identity-guard (T08.1a PR #3571 merged; T08.1b PR not opened) | `d397656c7f597d72d6a6c92676cd204aff72d4d8` for T08.1a | EVIDENCE.md#t08.1b-v1-identity-guard |
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
- PR #3557/T07 and PR #3571/T08.1a are confirmed MERGED. #3571 exact head was `5ac829ba203dbd3b6805eb8ad30b95d9e4aa1a31`; merge commit is `d397656c7f597d72d6a6c92676cd204aff72d4d8`. Its backend-focused local tests and exact-head applicable CI are recorded in earlier EVIDENCE entries; no v1 flag activation or deployment occurred.
- T08.1b source audit found the quota-reset risk: active-only lookup followed by a v1 zero-counter insert could shadow an inactive row with the same identity. Shared policy now checks all doctor/day/tag or resource/day rows before selecting a new v1 snapshot. Runtime constructors using the common snapshot pass the date. The Admin retention endpoint deletes only rows older than a cutoff with `days_to_keep >= 1`, so it cannot delete today's/future queue; past-day online admission is already rejected. Backup restore preserves policy/count and is a recovery path, not an admission writer. No ordinary counter/version mutation writer was found.
- Validation on current code: `test_daily_queue_creation_policy.py` — 11 passed / 1 warning; queue API, queue limits, visit confirmation, force majeure, GraphQL claim and canonical quota modules — 36 passed / 1 warning. Scoped Ruff check, Ruff format check for three focused files, compileall and `git diff --check` pass. PR-body quality gate passed (19 unit checks plus documented samples and this body). SQLite fixture only; no PostgreSQL race proof.
- No PR opened yet. `QUEUE_POLICY_V2_CREATION_ENABLED` remains default-off. Staging, production and patient data were not used.
- Blocker: none found in the bounded T08.1b identity slice. T08.2 adapter/report parity and T08.3 PostgreSQL concurrency/replay/partial-result proof remain mandatory before v1 rollout.
- Next exact action: finish full final diff review, then commit/push T08.1b and open its single-purpose PR. Confirm exact-head CI before continuing.
- Checks to rerun after any further runtime edit: policy suite, the six queue API/limits/visit/force-majeure/GraphQL/token suites, scoped Ruff, compileall and `git diff --check`. PostgreSQL concurrency proof remains T08.3.
## Checkpoint rules for the next agent

- Read RESUME, the canonical plan, this file, DECISIONS and current-task EVIDENCE before edits; pass the exact plan path to aif-implement.
- Preserve T00–T05 MERGED and exact merge SHAs. Never reset the registry to the initial all-PLANNED template or act on obsolete T03/T05 PR_OPEN journal entries.
- Record task/subtask, actual worktree/HEAD/diff/PR, anchors, scope, mode, validation and next action before edits and after meaningful checks.
- Keep deferrals PR-specific and distinguish accepted from passed. Record required NOT_RUN checks openly.
- Preserve unrelated local changes/scratch. Do not retry blocked deletion via an alternative method or discard the source T03 docs diff after recovering it here.

- Latest review/fix checkpoint (2026-10-03): deterministic baseline reproduction confirmed a new token entry could be created at 09:00:01 after passing the 09:00 gate at 08:59:59 and waiting for the numbering row lock. Fix commit `4595d67a6e484bab8a9a59277bdaf2775e143d56` locks and refreshes the queue before the gate. Regression now rejects both tagged and untagged queues without entry or usage increment. See `EVIDENCE.md#t07-token-cutoff-lock-review-fix`.
- Next exact action: update PR body with this Admin staging result and exact-head CI, commit and push the evidence checkpoint, then inspect checks for the actual pushed HEAD. Keep merge on hold pending independent human review and remaining Tier 2 or an explicit #3557-specific deferral. Do not begin T08.
