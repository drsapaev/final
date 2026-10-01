# Progress

Plan version: 1.1
Execution permission: IMPLEMENTATION_ACTIVE — user resumed the full plan on 2026-10-01
Start here: this file; use `EVIDENCE.md` for task history
Canonical plan: [codex-admin-queue-simplification.md](../codex-admin-queue-simplification.md)
Current task: T05
Current status: VALIDATED
Worktree: `C:\final\_wt_aqs_t05_settings_cache`
Branch: `codex/aqs-T05-settings-cache`
Base commit: `ecc14b05411c7e7b54efca2966416cd6a69df37c`
Current commit: `47276d178972226b0bcf561bdf8fa26a6940b913` (T05 implementation; locally validated)
Last updated: 2026-10-01T15:24:31+05:00

> **Возобновлено пользователем 2026-10-01:** «Продолжай реализации плана». T03 завершён: PR #3540 слит после исправления P1 и code-review verdict APPROVE. Tier 2 для #3540 остаётся принятым deferral, не пройденным тестовым набором.

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00 | MERGED | `codex/aqs-T00-docs` / [PR #3536](https://github.com/drsapaev/final/pull/3536) | `bae927f5c88010808d9091e7f47d09bbfdfa1005` | `EVIDENCE.md#t00` |
| T01 | MERGED | `codex/aqs-T01-profile-modal` / [PR #3537](https://github.com/drsapaev/final/pull/3537) | `967bd398c14bce4b835bd5be1205532387e2a909` | `EVIDENCE.md#t01` |
| T02 | MERGED | `codex/aqs-T02-queue-settings-state` / [PR #3538](https://github.com/drsapaev/final/pull/3538) | `b4ba6320797f056da19bbdc5cc672b3a97d2091e` | `EVIDENCE.md#t02` |
| T03 | MERGED | `codex/aqs-T03-cabinet-read` / [PR #3540](https://github.com/drsapaev/final/pull/3540) | `1e781da72bd927926b538b139a6c251cd09848b5` | `EVIDENCE.md#t03-merge-checkpoint` |
| T04 | MERGED | `codex/aqs-T04-empty-profiles` / [PR #3541](https://github.com/drsapaev/final/pull/3541) | `ecc14b05411c7e7b54efca2966416cd6a69df37c` | `EVIDENCE.md#t04-merge-checkpoint` |
| T05 | VALIDATED | `codex/aqs-T05-settings-cache` | | `EVIDENCE.md#t05-implementation-commit` |
| T06 | PLANNED | | | |
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

- Completed: T00–T04 are MERGED. T03 PR #3540 merged at `1e781da72bd927926b538b139a6c251cd09848b5`; its Tier 2 deferral remains accepted but unrun. T04 PR #3541 merged at `ecc14b05411c7e7b54efca2966416cd6a69df37c` after the user explicitly accepted its separate Tier 2 deferral and authorized merge; record that deferral as accepted, not passed. See `EVIDENCE.md#t04-merge-checkpoint`.
- Current task: T05, remove the queue service's process-lifetime settings cache. Canonical anchors: `backend/app/services/queue_svc/_core.py`, its composed service in `backend/app/services/queue_svc/__init__.py`, and settings-consuming command entrypoints in `backend/app/services/queue_svc/_operations.py`. Backward-compatible singleton is `backend/app/services/queue_service.py`.
- Confirmed baseline: `_load_queue_settings()` stores the first `get_queue_settings(db)` result on the singleton in `_cached_settings`; subsequent commands continue receiving it after an admin save. Two integration tests manually clear that private field, masking the stale-settings defect. Nested QR/join operations read settings through more than one service method, so the replacement must refresh at each top-level command while reusing one task-local snapshot through nested methods for the same service and DB session.
- Execution mode: `gate_known_root_cause`; the mandatory queue command gate ran from this worktree with `backend/app/services/queue_svc/_core.py` as the confirmed root. It returned `result=narrow_override`, `mode=execute`, `handoff_required=false`, `gate_misroute=false`, `override_used=true`; the known root was included in first-touch. The reason is recorded in `EVIDENCE.md#t05-kickoff`. The gate list only included `_core.py`; source inspection establishes that direct command consumers in `_operations.py`, focused tests, and this ledger also need changes for the plan's per-command behavior. No schema, ownership, admission policy, or clinical lifecycle change is included.
- T05 first-touch scope: settings snapshot context/helper in `_core.py`; decorators on settings-consuming public command methods in `_operations.py`; pass the existing settings snapshot through `effective_day_start_number()` in `backend/app/crud/queue_resource_routing.py`; remove duplicate `_cached_settings` initialization in `__init__.py`; focused backend regressions; remove the two test-only cache-reset workarounds; and update this ledger. This CRUD helper was initially a read-only reference; source review found its direct re-read would violate the same-snapshot contract, so the scope refinement is recorded in `EVIDENCE.md#t05-scope-refinement`. Denied: migrations/schema, queue ownership/fairness, numbering algorithm/history, quota/cutoff/admission policy, profile lifecycle, APIs/UI, production/staging data, unrelated cleanup.
- Validation target: first reproduce stale refresh with the same service instance; then verify new commands observe changed defaults, nested command calls and the day-start-number helper share one settings snapshot, exceptions release command-local context, and an existing daily queue keeps its saved values. Run focused backend tests, directly relevant integration tests only if their required PostgreSQL environment is available, `git diff --check`, and scoped quality checks.
- Stop condition: stop if consistent command boundaries require broad endpoint/service orchestration changes beyond queue service methods, if any existing daily snapshot would need rewriting, or if the fix changes ownership, numbering history, admission semantics, or schema.
- Completed for T05 so far: the regression failed before the runtime patch because a new-day queue still used `07:00` after the saved clinic setting changed to `08:00`. Implemented a task-local settings snapshot keyed by service instance and DB session; nested queue/token commands share it and each new command gets a fresh snapshot. Queue creation now passes that same snapshot into `effective_day_start_number()` for its `start_number`. Removed both duplicate `_cached_settings` initializers and the two integration-test cache-reset workarounds. The regression writes/updates real `ClinicSettings` rows, verifies existing queue time/number snapshots stay fixed, and verifies the next day's queue uses the updated time and start number.
- Validation run: focused backend tests PASS (24 passed, 1 warning); `py_compile` PASS; Ruff scoped to touched files with pre-existing C416 ignored PASS; Black `--check` on the regression and changed CRUD helper PASS; applicable pre-commit hooks PASS; `git diff --check` PASS. Full commands and limitations are in `EVIDENCE.md#t05-initial-validation`, `#t05-scope-refinement-validation`, and `#t05-precommit-checkpoint`.
- Environment/limitations: tests ran on Python 3.11.9 with their own isolated SQLite fixture. Staging Compose is stopped (no containers); disposable PostgreSQL was not available/used, so PostgreSQL integration files whose fixture requires that server are `NOT_RUN`. No production data was queried. Full-file Black check reports legacy formatting drift in five touched files; broad formatting-only churn (more than 1,000 diff lines reported) was not applied. Ordinary Ruff still reports two pre-existing C416 findings in unrelated `_operations.py` expressions; the new imports/code pass when those are excluded.
- Changed but not fully verified: the committed implementation and focused local checks are verified. PostgreSQL integration/staging checks remain `NOT_RUN`; remote PR checks and review are pending.
- Remaining: push T05, open its draft PR, then complete current-head checks and review. Do not start T06 until T05 is green, merged, and the worktree/branch are synchronized.
- Blocker: no implementation blocker. PostgreSQL integration validation is unavailable because staging is stopped; record it as `NOT_RUN`, not PASS. Stop if review shows the command boundary must move into endpoint-wide orchestration.
- Next exact action: push `codex/aqs-T05-settings-cache` and open a draft PR; update this ledger with its URL/head after creation.
- Checks to rerun after the next change: after PR creation, inspect current-head CI and code review; rerun local checks only if source changes.

## Checkpoint rules for the next agent

- Read the canonical plan, this file, DECISIONS and current-task EVIDENCE before edits; use the explicit plan path with aif-implement.
- Preserve T00–T04 MERGED and the exact current T05 checkpoint. Never reset the registry to the initial all-PLANNED template.
- Record the exact task/subtask, source anchors, first-touch allowlist, denied paths, command/result/SHA and next action before starting and after each meaningful check.
- Before ending a session or cleaning a branch, preserve local docs changes. Do not delete this worktree while version 1.1 exists only locally.
