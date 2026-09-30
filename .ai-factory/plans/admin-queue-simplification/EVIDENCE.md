# Evidence log

Do not put secrets, patient data, tokens or full network payloads here. Record exact commands, results and limitations. Update after each meaningful validation and before handing off.

## T00 — 2026-09-30

- Commit under test: `8bb1bdff5ce68627fe29eb227c03bb7ea0f9d1be` (`origin/main` fetched from `07ea63368989290318212635a7ab3a3bc2ed756d`).
- Environment: Windows worktree `C:\final\_wt_aqs_t00`; branch `codex/aqs-T00-docs`; WSL2 Ubuntu Docker is available, staging project is stopped.
- Execution mode: documentation-only PR; no runtime files touched.
- Allowed paths: `.ai-factory/plans/codex-admin-queue-simplification.md`; `.ai-factory/plans/admin-queue-simplification/{PROGRESS,DECISIONS,EVIDENCE}.md`.
- Denied paths: application code, tests, migrations, production data/configuration, other plans and generated output.
- Actual changed paths: `.ai-factory/plans/codex-admin-queue-simplification.md`; `.ai-factory/plans/admin-queue-simplification/{PROGRESS,DECISIONS,EVIDENCE}.md`.
- Original failure: N/A (documentation checkpoint).
- Initial status: main checkout clean on `main`; worktree created from fresh `origin/main`.
- Admission-writer inventory from source search (T08 must still confirm the final transaction boundaries): QR token/session joins at `backend/app/api/v1/endpoints/qr_queue/_join.py` and `backend/app/services/qr_queue/_sessions.py`; permanent-address entry is a QR session using the same queue-domain allocation path; legacy token endpoint `backend/app/api/v1/endpoints/queue.py`; compatibility endpoint `backend/app/api/v1/endpoints/online_queue_new.py`; GraphQL `backend/app/graphql/mutations.py`; Telegram adapter `backend/app/services/telegram/bot.py` delegates to queue service. Registrar/manual creation paths found at `registrar_integration/_today_queues.py`, `registrar_wizard/`, `batch_patient_service.py`, `visit_confirmation_service.py`, and `queue_batch_service.py`; these need source-audit confirmation as staff-created work and must not consume online quota. Deprecated older online-queue router is commented out in `api.py`. Token generation itself is not issuance; trace token-based joins to the same admission boundary. Queue transfer/clone paths must not increment.
- Configuration inventory: no live or production configuration was queried. Synthetic cases to build/verify: standalone profile; explicit missing parent; own-key parent conflict; mixed public directions; precreated future daily queue; inactive daily row with same canonical identity.
- Staging check: Windows `docker` CLI is not on PATH. WSL command `wsl.exe -d Ubuntu-24.04 -- docker compose -f /mnt/c/final/_wt_aqs_t00/ops/compose.staging.yml ps` exited 0 and showed the compose project has no running services. Compose emitted warnings for unset variable names; no env file or secret values were read or recorded. Staging runtime tests: `NOT_RUN`.
- Disposable PostgreSQL: `NOT_RUN`; no isolated staging database is running. This is not required to validate this docs-only PR.
- Validation: `git diff --cached --check` passed after removing five Markdown hard-break spaces found by the first check. All applicable pre-commit hooks passed across targeted invocations on the same four-file staged content: `check-added-large-files` and `gitleaks` passed using the existing user cache; `check-merge-conflict`, `detect-private-key`, `end-of-file-fixer`, `trailing-whitespace`, and `no-commit-to-branch` passed using a worktree-local cache. Format/language hooks and local guards had no matching files.
- Hook environment limitation: the initial hook invocation from the user cache hit Windows `WinError 4551` on several hook executables. With a worktree cache those checks passed, but initializing the gitleaks Go environment there was blocked when App Control denied generated `asm.exe`; gitleaks then passed against the same content using the existing cache. No hook was treated as passed solely from a skipped result.
- Result: PASS for docs formatting/scope and applicable hook checks. Runtime tests and browser checks `NOT_RUN` because this is docs-only and staging is stopped.
- Relevant output/artifact: command output retained in task transcript; do not copy environment secrets.
- Scope check: no production config or patient data accessed.
- Remaining limitation: confirm every writer's transaction boundary during T08; staging/browser/runtime checks were not performed.
- PR: [#3536](https://github.com/drsapaev/final/pull/3536), merged after the PR body quality gate was corrected and the latest review-quality check passed.
- Merge commit: `bae927f5c88010808d9091e7f47d09bbfdfa1005`.

## T01 — 2026-09-30

- Commits under test: initial implementation `9ca4573a5`; CI ratchet correction `6b8f2b7e9`; both based on `bae927f5c88010808d9091e7f47d09bbfdfa1005`.
- Environment: Windows worktree `C:\final\_wt_aqs_t01`; branch `codex/aqs-T01-profile-modal`.
- Execution mode: `advisory_gate`; narrow UI-only task, no backend/API/schema/lifecycle edits.
- Allowed paths: `frontend/src/components/admin/QueueProfilesManager.tsx`; admin-local persisted palette constants in `frontend/src/components/admin/queueProfileColors.ts` (added to resolve a measured UI baseline regression); focused component test under `frontend/src/components/admin/__tests__/`; necessary rules in `frontend/src/components/admin/admin.css`; this progress/evidence ledger.
- Denied paths: backend, API schemas/contracts, migrations, route registry, queue/profile business semantics, unrelated UI and generated output.
- Original failure: the new focused component tests failed against the pre-change source: status selection filtered out every row; spaces closed the form; no accessible modal/focus behavior existed; color presets were CSS variables rather than usable hex values; form labels had no control association.
- Validation commands and results:
  - `npm.cmd run test:run -- src/components/admin/__tests__/QueueProfilesManager.interactions.test.tsx src/components/admin/__tests__/QueueProfilesManager.csv.test.tsx` — PASS, 13/13 tests.
  - `npm.cmd run type-check` — PASS.
  - `npx.cmd --no-install eslint src/components/admin/QueueProfilesManager.tsx src/components/admin/queueProfileColors.ts src/components/admin/__tests__/QueueProfilesManager.interactions.test.tsx` — PASS, 0 errors; the component retains four pre-existing warnings and the persisted palette has a scoped suppression.
  - `npx.cmd --no-install stylelint src/components/admin/admin.css` — PASS.
  - `npm.cmd run build` — PASS; build emitted existing `marginBottom`/`flexWrap` CSS-property warnings from generated/minified CSS.
  - `git diff --check` — PASS.
- Pre-commit results on the original five-file scope (palette helper added after the CI ratchet check):
  - `check-added-large-files` — PASS.
  - `gitleaks` — PASS using the existing user cache.
  - Merge-conflict, private-key, end-of-file, trailing-whitespace, and no-commit-to-branch hooks — PASS after the trailing-whitespace hook normalized two comment lines and those lines were re-staged.
  - The repository's `eslint` pre-commit wrapper — FAILS before linting with ESLint 9 error `patterns must be a non-empty string or an array of non-empty strings`; the same scoped ESLint command run directly from `frontend/` passes with 0 errors and 4 pre-existing warnings. No shared hook configuration was changed because that is outside T01 scope.
- Commit: `9ca4573a5` (`fix(queue): repair profile form interactions`). Commit hooks passed except the three individually validated hooks (`check-added-large-files`, `gitleaks`, direct scoped ESLint), which were skipped in the hook process because the ESLint wrapper fails before linting; all remaining applicable hooks passed.
- Result: PASS for local T01 validation.
- Relevant output or artifact: Vitest uses synthetic profiles only; CSV suite emitted its expected synthetic network-failure log in the test that verifies per-profile errors.
- Actual changed paths: `frontend/src/components/admin/QueueProfilesManager.tsx`; `frontend/src/components/admin/queueProfileColors.ts`; `frontend/src/components/admin/admin.css`; `frontend/src/components/admin/__tests__/QueueProfilesManager.interactions.test.tsx`; this plan's `PROGRESS.md` and `EVIDENCE.md`.
- Scope check: no profile semantics, backend, API contract, schema, routing, or queue behavior changed. Filter now consumes `Select.onValueChange`; API's max-20 hex color contract was checked in source. No network/load path changed.
- Remaining limitation: live browser visual QA and first-row cold/repeat timing are deferred to T18 synthetic-staging acceptance; staging was stopped at T00. No production data was accessed.
- PR: [#3537](https://github.com/drsapaev/final/pull/3537), merged by squash from `codex/aqs-T01-profile-modal` after current-head checks passed. PR review-quality body gate passed locally using `scripts/check_pr_review_template.py`.
- Merge commit: `967bd398c14bce4b835bd5be1205532387e2a909`.

### CI ratchet correction — 2026-09-30

- The first PR check for `Regression Audit Gate` failed: `tsxHex` increased from 384 to 387 and `isDarkBranches` from 105 to 106.
- Cause: placing three new persisted hex values in TSX and duplicating the theme conditional on the shared Dialog.
- Correction: moved the palette into `queueProfileColors.ts` with a scoped lint suppression explaining that these values are persisted API data, and let shared Dialog use its design token background instead of adding another theme branch.
- Correction commit: `6b8f2b7e9` (`fix(queue): satisfy admin UI baseline ratchet`); pushed to PR #3537. PR description records the red check and fix.
- Validation after correction: `node scripts/ui-baseline.mjs --check` PASS (`tsxHex` 384→379, `inlineStyles` 2471→2242, `isDarkBranches` 105→104, and no ratchet regressions); targeted Vitest 13/13 PASS; type-check PASS; scoped ESLint PASS with zero errors and the same four pre-existing component warnings; stylelint PASS; build PASS with existing CSS minifier warnings.
- The corrected PR head had CI checks pending at the first status snapshot; those checks must finish before merge. The prior red run is preserved here as handled evidence.

### Final CI and merge evidence — T01 — 2026-09-30

- The first complete frontend E2E run had one unrelated Lab dirty-guard timeout (60/61 passed, WebSocket proxy logged ECONNREFUSED); the failed job was rerun on the same PR head and passed (61/61, 13m28s).
- All required PR checks on head `225d66a7b490bf9d1af69a057532efa72158e02c` passed, including frontend E2E, unit/build/type checks, PR gates, CodeQL and security scans. Scope-specific skipped jobs were expected for UI-only work.
- Merge verified through GitHub API with matching head SHA; squash merge commit: `967bd398c14bce4b835bd5be1205532387e2a909`. Remote T01 branch was deleted. Main fast-forwarded from `bae927f5c88010808d9091e7f47d09bbfdfa1005` to this merge commit.

## T02 — 2026-09-30 — IN_PROGRESS

- Commit under test: clean base `967bd398c14bce4b835bd5be1205532387e2a909`; no implementation commit yet.
- Environment: Windows managed worktree `C:\Users\DrSapaev\.codex\worktrees\aqs-t02-settings-state\final`; branch `codex/aqs-T02-queue-settings-state` created from `origin/main` at the base above.
- Execution mode: `advisory_gate`; narrow Admin UI state handling, no API or runtime changes. Gate command not run because the advisory mode makes it optional and source/tests provide the anchors.
- Allowed paths: `frontend/src/components/admin/QueueSettings.tsx`; focused test coverage in `frontend/src/components/admin/__tests__/QueueSettings.effective.test.tsx`; relevant five locale files for localized truthful status/hints; this plan's `PROGRESS.md` and `EVIDENCE.md`. After UI-ratchet evidence showed the removed Dev Mode JSX was the sole source of three CSS variable assignments, narrowly extend T02 to the now-unused `.admin-dev-mode-card` and `.admin-dev-mode-btn` selectors in `frontend/src/components/admin/admin.css` only.
- Denied paths: backend/API, schemas/contracts, migrations, queue runtime/business logic, routing, deployment, unrelated screens, generated output.
- Canonical anchors: `frontend/src/components/admin/QueueSettings.tsx`; existing read-only GET `/admin/queue/settings/effective` and tests; backend `admin_clinic.py` and `crud/clinic.py` read-only references for GET/PUT shape; `frontend/DESIGN_SYSTEM.md` UI Layer Contract; clinic queue simplification plan decisions D1–D5.
- Original behavior confirmed by source: settings GET failure leaves fallback controls and active Save; max-per-day absent from the GET displays fabricated `1`; calculated number-range UI displays synthetic values; `dev_mode_enabled` is included in frontend payload; `testQueueGeneration` issues `POST /admin/queue/test`; close-time hint implies behavior while the existing effective report marks it not live.
- Validation target: add regression tests before implementation and confirm them red; then run focused Vitest, type-check, scoped ESLint, build if needed, `git diff --check`, and applicable hooks.
- Stop condition: stop before touching backend/API/queue runtime if source shows frontend-only changes cannot provide the planned behavior.
- Result: implementation complete; local validation passed. Commit/PR pending.
- PR / merge commit: pending.

### T02 local validation — 2026-09-30

- Commit under test: working tree based on `967bd398c14bce4b835bd5be1205532387e2a909`; implementation is not committed yet.
- Original failure: source inspection confirmed failed settings GET used fallback controls with active Save; a missing per-profile quota rendered as `1`; the view displayed synthetic number ranges; `dev_mode_enabled` entered the PUT payload; and the “test” action called mutating `POST /admin/queue/test`. The close-time hint implied runtime behavior while the effective-settings report marked it display-only.
- Validation commands and results:
  - `npx.cmd --no-install vitest run src/components/admin/__tests__/QueueSettings.effective.test.tsx` — PASS, 24/24 tests, including retry after a confirmed discard whose GET fails.
  - `npm.cmd run type-check -- --pretty false` — PASS.
  - `npx.cmd --no-install eslint src/components/admin/QueueSettings.tsx src/components/admin/__tests__/QueueSettings.effective.test.tsx` — PASS, no diagnostics.
  - `npx.cmd --no-install stylelint src/components/admin/admin.css` — PASS.
  - `npm.cmd run build` — PASS after the final component/CSS changes; existing CSS minifier warnings for camelCase `marginBottom` and `flexWrap` remain unrelated.
  - `node scripts/ui-baseline.mjs --check` — PASS after removing the two now-unused Dev Mode CSS selectors. The first run found only three newly orphaned `--admin-*` custom-property references; repository search confirmed their selectors had no remaining JSX users. Removing that dead block reduced undefined-variable names from 152 to 149; the full ratchet then passed.
  - `git diff --check` — PASS.
- Actual changed paths: `frontend/src/components/admin/QueueSettings.tsx`; `frontend/src/components/admin/__tests__/QueueSettings.effective.test.tsx`; `frontend/src/components/admin/admin.css`; `frontend/src/i18n/locales/{ru,en,uz-Latn,uz-Cyrl,kk}.ts`; this plan's `PROGRESS.md` and `EVIDENCE.md`.
- Scope check: no backend/API schema, migration, queue runtime, route, or deployment changes. `max_per_day=0` behavior remains a later runtime task (T08); T02 only removes fabricated UI defaults. Existing daily snapshot/report remains read-only. Removed CSS selectors were confirmed unused after the Dev Mode JSX removal.
- Remaining limitation: no live browser/visual QA or staging check for this UI-only task; the full end-to-end admin workflow remains T18. Vitest reports existing shared `ConfirmDialog`/Modal `closable` DOM warning while the new confirmation path is rendered; tests pass and common dialog internals are outside this task's allowed scope.
- PR: pending.
- Merge commit: pending.

### T02 pre-commit check — 2026-09-30

- `check-added-large-files`, merge-conflict, private-key, end-of-file, branch guard, and `gitleaks` hooks passed on the commit attempt.
- `trailing-whitespace` found and automatically removed blank trailing spaces in `QueueSettings.tsx`; the file was re-staged and `git diff --cached --check` passed afterward.
- The repository ESLint pre-commit wrapper failed before linting because it searched for `frontend/src/...` paths from `frontend/` and reported “No files matching the pattern”. The identical scoped ESLint command run directly from `frontend/` passed with no diagnostics after the hook's whitespace-only edit. For the retry, skip only the two individually resolved hooks (`trailing-whitespace` after its fix, `eslint` due to the wrapper path bug); all other hooks remain enabled.
