# Progress

Plan version: 1.1
Execution permission: IMPLEMENTATION_ACTIVE — user resumed the full plan on 2026-10-01
Start here: this file; use `EVIDENCE.md` for task history
Canonical plan: [codex-admin-queue-simplification.md](../codex-admin-queue-simplification.md)
Current task: T04
Current status: PR_OPEN
Worktree: `C:\final\_wt_aqs_t04_empty_profiles`
Branch: `codex/aqs-T04-empty-profiles`
Base commit: `1e781da72bd927926b538b139a6c251cd09848b5`
Current commit: `560860f724bf87874ed474bbe50cb5db1a245dd3` (PR head checked; latest code/test checkpoint is `77783b8a1d7c54843b3b47a257e5a45d10439a2f`)
Last updated: 2026-10-01T13:19:52+05:00

> **Возобновлено пользователем 2026-10-01:** «Продолжай реализации плана». T03 завершён: PR #3540 слит после исправления P1 и code-review verdict APPROVE. Tier 2 для #3540 остаётся принятым deferral, не пройденным тестовым набором.

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00 | MERGED | `codex/aqs-T00-docs` / [PR #3536](https://github.com/drsapaev/final/pull/3536) | `bae927f5c88010808d9091e7f47d09bbfdfa1005` | `EVIDENCE.md#t00` |
| T01 | MERGED | `codex/aqs-T01-profile-modal` / [PR #3537](https://github.com/drsapaev/final/pull/3537) | `967bd398c14bce4b835bd5be1205532387e2a909` | `EVIDENCE.md#t01` |
| T02 | MERGED | `codex/aqs-T02-queue-settings-state` / [PR #3538](https://github.com/drsapaev/final/pull/3538) | `b4ba6320797f056da19bbdc5cc672b3a97d2091e` | `EVIDENCE.md#t02` |
| T03 | MERGED | `codex/aqs-T03-cabinet-read` / [PR #3540](https://github.com/drsapaev/final/pull/3540) | `1e781da72bd927926b538b139a6c251cd09848b5` | `EVIDENCE.md#t03-merge-checkpoint` |
| T04 | PR_OPEN | `codex/aqs-T04-empty-profiles` / [PR #3541](https://github.com/drsapaev/final/pull/3541) | | `EVIDENCE.md#t04-pr-open` |
| T05 | PLANNED | | | |
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

- Completed: T00–T03 are MERGED. T03 PR #3540 merged at `1e781da72bd927926b538b139a6c251cd09848b5`; the user approved follow-up `e18d2e2c` with P0/P1/P2 all zero. T03 Tier 2 remains formally deferred and unpassed; its reason, evidence, owner, and resume condition are recorded in the PR. See `EVIDENCE.md#t03-merge-checkpoint`.
- Current task: T04, remove runtime fallback restoration of built-in queue profiles. Canonical anchors: `backend/app/api/v1/endpoints/registrar_integration/_queue_profiles.py`, `frontend/src/components/navigation/Tabs.tsx`, and the explicit initial seed in Alembic `0055_queue_resource_provisioning.py`.
- Confirmed baseline: both admin and public GET endpoints returned `success: true` with `INITIAL_QUEUE_PROFILES` when the query was empty and did the same after read exceptions. `Tabs.tsx` treated a valid empty response as an exception and substituted six hardcoded tabs on failure. Migration 0055 explicitly seeds the initial catalog; it remains unchanged.
- Execution mode: `advisory_gate` under the GPT-6 UI/API exception. The known-root `agent_gate` run returned only `_queue_profiles.py` plus `py_compile` (`gate_misroute=false`, `result=narrow_override`, `override_used=true`); this output is advisory and does not replace the manually declared task scope.
- T04 first-touch scope: the two profile read functions, the `Tabs.tsx` fallback and its focused tests, backend read-contract tests, the obsolete static fallback-marker assertion, and this progress/evidence ledger. After full-suite evidence, `frontend/src/pages/registrar/views/__tests__/WorklistView.tabpanel.test.tsx` was added as the directly dependent consumer test whose mock assumed the removed six-tab fallback. Final diff review found a stale empty-catalog assertion in `backend/tests/integration/test_specialty_canonicalization.py` and an outdated comment in `backend/tests/integration/test_rq16b_direction_entry_methods.py` describing the removed public-read fallback; both are now in scope for narrow contract/documentation updates. Denied areas remain untouched: schema/migrations, profile writes, role/RBAC, queue admission/join/token logic, QR ownership/eligibility, route registry, and unrelated wizard fallbacks.
- Completed for T04: fresh worktree from `origin/main` at `1e781da72`; canonical/legacy and seed paths inspected; red-first backend tests reproduced the fallback/error behavior; endpoint and UI fixes added; the old dependent fixture now supplies one explicit `ecg` backend profile. Focused backend/frontend tests, full Vitest (311 files / 2,880 tests), strict type check, full lint, theme and icon-control checks, production build, and all 86 Chromium tests across the six Tier 1 specs passed. Exact commands and environment notes are in `EVIDENCE.md#t04-final-validation`.
- Validation notes: full lint exited 0 with 0 errors and 3,514 warnings. Direct scoped ESLint passed; the repository's local ESLint pre-commit hook has a path mismatch after changing directory to `frontend`, reproduced on the implementation and final test/evidence commits. Only that hook is skipped on retry; all other hooks remain enabled. Pinned Ruff-format and Black hooks passed after their formatting-only changes. The first Windows browser run lacked platform-specific Win32 snapshots; generated untracked images were removed. The complete browser suite passed against checked-in Linux baselines in an isolated WSL ext4 copy; no snapshots or package manifests were changed.
- Resolved finding: the empty-catalog integration test now asserts `success`, `profiles == []`, and `source == "database"`; the separate database-backed test still verifies canonical `settings_key`. The stale comment in `test_rq16b_direction_entry_methods.py` now distinguishes the removed public-read fallback from that test's independent archived-key guard.
- Remaining: the current PR head's applicable GitHub checks passed. The PR has no review decision; obtain reviewer acknowledgment for the separate T04 Tier 2 deferral, then complete the merge cycle.
- Blocker: PR #3541 is open with no review decision. Tier 2 remains NOT RUN and reviewer acknowledgment is pending; do not merge until the deferral is acknowledged. Skipped workflow jobs are recorded as skipped, not passes. Stop if the fix requires changing a join/admission contract, auth/RBAC, or seeding behavior beyond migration 0055.
- Next exact action: commit/push the final evidence checkpoint, recheck checks on the resulting PR head, then obtain reviewer acknowledgment for T04's Tier 2 deferral. Keep the reviewer acknowledgment checkbox unchecked until the reviewer confirms it.
- The previous T03 worktree remains locally preserved with its separate documentation and QA scratch; it is not part of T04. Do not delete or overwrite those files during this task.

## Checkpoint rules for the next agent

- Read the canonical plan, this file, DECISIONS and current-task EVIDENCE before edits; use the explicit plan path with aif-implement.
- Preserve T00–T03 MERGED and T04's latest recorded state until live GitHub proves a different state. Never reset the registry to the initial all-PLANNED template.
- Record the exact task/subtask, source anchors, first-touch allowlist, denied paths, command/result/SHA and next action before starting and after each meaningful check.
- Before ending a session or cleaning a branch, preserve local docs changes. Do not delete this worktree while version 1.1 exists only locally.
