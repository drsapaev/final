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
- PR: pending.
- Merge commit: pending.
