# Progress

Plan version: 2.6
Execution permission: IMPLEMENTATION_ACTIVE — user resumed the full plan on 2026-10-01
Start here: [RESUME.md](RESUME.md), then this file and current-task EVIDENCE
Canonical plan: [codex-admin-queue-simplification.md](../codex-admin-queue-simplification.md)
Current task: T08.2b — source inventory of remaining active admission adapters
Current status: T08.2a / PR #3576 is user-confirmed MERGED at `1ed6d05874c2ea205a625bb70879adb10b077be4`. T08.2b source audit on `origin/main` `4e6f125f17c637fc27296e2d0ec9d23f5d376775` found the mounted legacy token, compatibility online, QR-session, and permanent-address paths delegate to `QueueBusinessService.join_queue_with_token`; GraphQL was the only confirmed independent successful writer and is now quota-aware. No T08.2b runtime patch is indicated. Main advanced through PR #3567 and #3580 to `c0ea82be6698828a3b040d9a516a48e132b8261d`; the branch has been rebased locally, preserving upstream Task 102 and this task as Task 103 in the DevBrain log. PR #3581 remains OPEN and needs a lease-guarded push against remote head `f40cf66ad3713c7a9a8141e35c3427beeaf4a094`, followed by exact-head checks. Do not mark T08.2b MERGED until its PR is merged.
Last completed task: T08.2a — MERGED (#3576, merge commit `1ed6d05874c2ea205a625bb70879adb10b077be4`)
Worktree: C:\final\_wt_aqs_t082b_admission
Branch: codex/aqs-T08.2b-admission
Base commit: c0ea82be6698828a3b040d9a516a48e132b8261d
Current code commit: rebased source inventory commit `66e0c6e48`; resolve the PR branch tip live because journal-only commits may follow it.
Last updated: 2026-10-03T23:29:58+05:00

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
| T08 | IN_PROGRESS | T08.1a/#3571, T08.1b/#3572 and T08.2a/#3576 MERGED; T08.2b PR #3581 OPEN | `1ed6d05874c2ea205a625bb70879adb10b077be4` | EVIDENCE.md#t08.2a-merge-and-t08.2b-source-inventory |
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

- User confirmed that they merged PR #3576 themselves. GitHub reports it merged at `1ed6d05874c2ea205a625bb70879adb10b077be4`; exact code HEAD was `35b6943cce8c0295b8e9a68077cb881c73fcda20`. Current base is fresh `origin/main` `4e6f125f17c637fc27296e2d0ec9d23f5d376775` in `C:\final\_wt_aqs_t082b_admission`.
- T08.2b source inventory: legacy `/queue/legacy/join`, mounted `/online-queue/join`, QR `/queue/join/complete` (single and multiple), and permanent-direction sessions all delegate successful admissions to `QueueBusinessService.join_queue_with_token`. It checks the DailyQueue lock-refreshed quota, increments v1 only for a new entry, and keeps entry/counter/session outcome in the existing transaction boundary. GraphQL was the only confirmed independent successful writer and is quota-aware after #3576.
- No additional active successful online-admission writer was found. The old `crud.online_queue.join_online_queue` has no app caller and its old router is not mounted. The Telegram callback is mounted but calls a missing `join_queue` method before any queue write. `/queue/open` creates/opens a queue but does not issue an entry; `QueueApiService` already takes the canonical daily-queue creation lock. Staff service additions, transfers and derivatives are not independent online issuances under D1 and do not increment the counter.
- T08.2b runtime patch: none indicated by source evidence. The evidence-only inventory and existing test anchors are recorded in `EVIDENCE.md`; no tests were run because no runtime or test source changed. `git diff --check` passed after the inventory was written.
- Gate: first run routed the queue task to generic model/window and unrelated Telegram files. The only known-root retry used `backend/app/services/queue_svc/_operations.py`, returned `narrow_override`, and still included unrelated paths. The user-approved T08 plan and required coverage table are the manual basis for the narrow docs-only checkpoint; no additional gate run is permitted.
- PostgreSQL concurrency/replay/partial-result proof remains T08.3. T08.2c reporting parity is still planned. `QUEUE_POLICY_V2_CREATION_ENABLED` remains default-off; no staging or production work was performed.
- The repository PR-body quality gate passed: 19 unit checks, both documented samples, and this PR body.
- Next exact action: commit and push the rebase-resolution checkpoint with a lease against remote PR head `f40cf66ad3713c7a9a8141e35c3427beeaf4a094`, verify the live PR base/head, and wait for applicable checks. After merge, start T08.2c from fresh `origin/main`.

### Historical completed context (T08.2a and earlier)

> Superseded: the T08.2a PR #3576 is merged. The older OPEN/checks-pending instructions below are retained as history only; do not resume them. Continue from the current T08.2b checkpoint above.

- T08.1b / PR #3572 is confirmed MERGED at `95ff3b4752a091f22f9702977d611a3b6d9f1595`; its exact-head applicable CI passed on `6df007c7f63c0ce7be40ac9a6f70c9524fddca65`. Backend tests, PR Required Gate, CodeQL, gitleaks, security scan, parity and quality passed; path-aware frontend jobs were skipped, not passed. PostgreSQL concurrency and staging remain NOT_RUN. The v1 creation flag remains default-off.
- T08.2a is the first bounded slice of T08.2: align the direct GraphQL `Mutation._join_queue_impl` writer with the canonical v1 issuance counter. Preserve GraphQL's current lock order, claim/duplicate handling, clinic-local time window, direct commit boundary, and legacy active-entry cap.
- Implementation: v1 checks `online_issued_count >= max_online_entries` (zero remains a closed cap) and increments only after adding a new online entry, before the existing commit. Legacy still counts waiting/called rows. T08.2a unit coverage is 7/7 and the GraphQL integration module is 17/17 on isolated SQLite fixtures.
- Gate: initial prompt routed to unrelated Telegram manager files despite the T08.2 GraphQL source anchor. The single retry with `backend/app/graphql/mutations.py` returned `narrow_override`, including the confirmed runtime file but omitting the planned regression test and evidence files. Narrow manual scope is based on the user-approved T08.2 contract; no third gate invocation.
- First-touch scope: `backend/app/graphql/mutations.py`; `backend/tests/unit/test_graphql_queue_claim_coordinator.py`; `backend/tests/integration/test_graphql_resolvers_real_db.py` for the plan-required full-schema/database check; `.ai-factory/plans/codex-admin-queue-simplification.md`; `.ai-factory/plans/admin-queue-simplification/{PROGRESS,RESUME,EVIDENCE}.md`; one factual append to `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md` because this is a confirmed gate-routing miss. No other adapter/report, Telegram runtime, schema, feature flag, staging or production paths.
- Validation: fail-first reproduced two v1 failures, then GraphQL unit 7/7 and integration module 17/17 passed; scoped Ruff, pinned pre-commit, compileall, `git diff --check` and PR-body gate (19 tests) passed. Ruff format check on the legacy integration file itself reports pre-existing unrelated formatting drift; no broad formatter rewrite was applied. PostgreSQL concurrency/replay/partial-result proof remains T08.3.
- Stop if GraphQL cannot keep the counter in the same existing transaction, a required lock-order change appears, another writer is discovered, or the GraphQL legacy/v1 cap contract is ambiguous.
- T07/PR #3557 is MERGED as 425df11c7a84f0d1e7954df0d00415927212669a; exact-head applicable CI finished 27 SUCCESS / 12 SKIPPED / 0 failures. Its three named Tier-2 deferrals remain NOT_RUN; full STAGING_VALIDATION remains mandatory before deployment.
- PR #3557/T07 and PR #3571/T08.1a are confirmed MERGED. #3571 exact head was `5ac829ba203dbd3b6805eb8ad30b95d9e4aa1a31`; merge commit is `d397656c7f597d72d6a6c92676cd204aff72d4d8`. Its backend-focused local tests and exact-head applicable CI are recorded in earlier EVIDENCE entries; no v1 flag activation or deployment occurred.
- T08.1b source audit found the quota-reset risk: active-only lookup followed by a v1 zero-counter insert could shadow an inactive row with the same identity. Shared policy now checks all doctor/day/tag or resource/day rows before selecting a new v1 snapshot. Runtime constructors using the common snapshot pass the date. The Admin retention endpoint deletes only rows older than a cutoff with `days_to_keep >= 1`, so it cannot delete today's/future queue; past-day online admission is already rejected. Backup restore preserves policy/count and is a recovery path, not an admission writer. No ordinary counter/version mutation writer was found.
- Validation on current code: `test_daily_queue_creation_policy.py` — 11 passed / 1 warning; queue API, queue limits, visit confirmation, force majeure, GraphQL claim and canonical quota modules — 36 passed / 1 warning. Ruff, Ruff format, Black, compileall and `git diff --check` pass. PR-body quality gate passed (19 unit checks plus documented samples and this body). SQLite fixture only; no PostgreSQL race proof.
- PR #3572 is MERGED at `95ff3b4752a091f22f9702977d611a3b6d9f1595`; the preceding “OPEN/checks pending” text is historical and superseded by the checkpoint above and the merge evidence entry.
- Blocker: none identified for T08.1b. Remaining T08.2 adapter/report parity and T08.3 PostgreSQL concurrency/replay/partial-result proof are still required before considering v1 rollout.
- Next exact action: re-read PR #3576's live HEAD and checks after this documentation checkpoint push; compare the PR HEAD with local `git rev-parse HEAD`, wait for all applicable checks and review, and fix in-scope failures in the same PR.
- Checks to rerun after any further runtime edit: policy suite, the six queue API/limits/visit/force-majeure/GraphQL/token suites, scoped Ruff, compileall and `git diff --check`. PostgreSQL concurrency proof remains T08.3.
## Checkpoint rules for the next agent

- Read RESUME, the canonical plan, this file, DECISIONS and current-task EVIDENCE before edits; pass the exact plan path to aif-implement.
- Preserve T00–T05 MERGED and exact merge SHAs. Never reset the registry to the initial all-PLANNED template or act on obsolete T03/T05 PR_OPEN journal entries.
- Record task/subtask, actual worktree/HEAD/diff/PR, anchors, scope, mode, validation and next action before edits and after meaningful checks.
- Keep deferrals PR-specific and distinguish accepted from passed. Record required NOT_RUN checks openly.
- Preserve unrelated local changes/scratch. Do not retry blocked deletion via an alternative method or discard the source T03 docs diff after recovering it here.

- Latest review/fix checkpoint (2026-10-03): deterministic baseline reproduction confirmed a new token entry could be created at 09:00:01 after passing the 09:00 gate at 08:59:59 and waiting for the numbering row lock. Fix commit `4595d67a6e484bab8a9a59277bdaf2775e143d56` locks and refreshes the queue before the gate. Regression now rejects both tagged and untagged queues without entry or usage increment. See `EVIDENCE.md#t07-token-cutoff-lock-review-fix`.
- Next exact action: update PR body with this Admin staging result and exact-head CI, commit and push the evidence checkpoint, then inspect checks for the actual pushed HEAD. Keep merge on hold pending independent human review and remaining Tier 2 or an explicit #3557-specific deferral. Do not begin T08.
