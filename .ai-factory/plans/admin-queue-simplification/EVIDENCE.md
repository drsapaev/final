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

- Commit under test: `9ca4573a5` based on `bae927f5c88010808d9091e7f47d09bbfdfa1005`.
- Environment: Windows worktree `C:\final\_wt_aqs_t01`; branch `codex/aqs-T01-profile-modal`.
- Execution mode: `advisory_gate`; narrow UI-only task, no backend/API/schema/lifecycle edits.
- Allowed paths: `frontend/src/components/admin/QueueProfilesManager.tsx`; focused component test under `frontend/src/components/admin/__tests__/`; necessary rules in `frontend/src/components/admin/admin.css`; this progress/evidence ledger.
- Denied paths: backend, API schemas/contracts, migrations, route registry, queue/profile business semantics, unrelated UI and generated output.
- Original failure: the new focused component tests failed against the pre-change source: status selection filtered out every row; spaces closed the form; no accessible modal/focus behavior existed; color presets were CSS variables rather than usable hex values; form labels had no control association.
- Validation commands and results:
  - `npm.cmd run test:run -- src/components/admin/__tests__/QueueProfilesManager.interactions.test.tsx src/components/admin/__tests__/QueueProfilesManager.csv.test.tsx` — PASS, 13/13 tests.
  - `npm.cmd run type-check` — PASS.
  - `npx.cmd --no-install eslint src/components/admin/QueueProfilesManager.tsx src/components/admin/__tests__/QueueProfilesManager.interactions.test.tsx` — PASS, 0 errors; 4 existing warnings remain for missing `t` dependency, old hex/rgba values outside the new palette, and their existing lines.
  - `npx.cmd --no-install stylelint src/components/admin/admin.css` — PASS.
  - `npm.cmd run build` — PASS; build emitted existing `marginBottom`/`flexWrap` CSS-property warnings from generated/minified CSS.
  - `git diff --check` — PASS.
- Pre-commit results on the final five-file scope:
  - `check-added-large-files` — PASS.
  - `gitleaks` — PASS using the existing user cache.
  - Merge-conflict, private-key, end-of-file, trailing-whitespace, and no-commit-to-branch hooks — PASS after the trailing-whitespace hook normalized two comment lines and those lines were re-staged.
  - The repository's `eslint` pre-commit wrapper — FAILS before linting with ESLint 9 error `patterns must be a non-empty string or an array of non-empty strings`; the same scoped ESLint command run directly from `frontend/` passes with 0 errors and 4 pre-existing warnings. No shared hook configuration was changed because that is outside T01 scope.
- Commit: `9ca4573a5` (`fix(queue): repair profile form interactions`). Commit hooks passed except the three individually validated hooks (`check-added-large-files`, `gitleaks`, direct scoped ESLint), which were skipped in the hook process because the ESLint wrapper fails before linting; all remaining applicable hooks passed.
- Result: PASS for local T01 validation.
- Relevant output or artifact: Vitest uses synthetic profiles only; CSV suite emitted its expected synthetic network-failure log in the test that verifies per-profile errors.
- Actual changed paths: `frontend/src/components/admin/QueueProfilesManager.tsx`; `frontend/src/components/admin/admin.css`; `frontend/src/components/admin/__tests__/QueueProfilesManager.interactions.test.tsx`; this plan's `PROGRESS.md` and `EVIDENCE.md`.
- Scope check: no profile semantics, backend, API contract, schema, routing, or queue behavior changed. Filter now consumes `Select.onValueChange`; API's max-20 hex color contract was checked in source. No network/load path changed.
- Remaining limitation: live browser visual QA and first-row cold/repeat timing are deferred to T18 synthetic-staging acceptance; staging was stopped at T00. No production data was accessed.
- PR: [#3537](https://github.com/drsapaev/final/pull/3537), opened from `codex/aqs-T01-profile-modal`; CI checks were pending at the first status snapshot. PR review-quality body gate passed locally using `scripts/check_pr_review_template.py`.
- Merge commit: pending.
