# WSL staging session guard

Base: `9a5404a5f9c339885662cc0b79a392cfd5b0e1f1`
Branch: `codex/wsl-staging-session-guard`
Status: PR_OPEN — [#3559](https://github.com/drsapaev/final/pull/3559). Separate from Admin Queue Simplification T07 / #3557.
Code commit: `4705d6873f1de342bff02b8bd430cb0b3d1a521a`; subsequent checkpoint commit is documentation only.

## Pre-work boundary

- Selected mode: `narrow_override` following two `gate_known_root_cause` runs.
- Reason: confirmed launcher owners; gate omitted the required helper and supporting tests/docs twice. Repo-approved basis: `docs/runbooks/AGENT_CYCLIC_WORKFLOW.md`, Relationship To Skills And Dev-Brain.
- Risk: staging lifecycle and isolation; no production configuration changes.
- Canonical anchors: `ops/compose.staging.yml`, `ops/scripts/start_staging.ps1`, `ops/scripts/stop_staging.ps1`, `scripts/run_backend_pytest.ps1`, worktree and staging runbooks.
- Allowed: the two launchers, new `ops/scripts/wsl_staging.ps1`, `scripts/wsl_staging.py`, focused `scripts/tests/test_wsl_staging_guard.py`, WSL staging runbook, corrected staging examples and compact project memory pointer, this evidence.
- Denied: Compose/runtime/model/migration/auth changes, other PR worktrees, global `.wslconfig`, distro shutdown, production requests, shared project/container mutations, secrets and patient payload.
- Validation: mocked native command/isolation/keeper/skip regressions, read-only Windows/WSL preflight, an owned minimal synthetic Docker contour only if needed, `git diff --check`.
- Stop: source mount/project ownership conflict; required scope expands into runtime or global host settings; mandatory validation cannot be performed.

## Findings

- T06/T07 records document expired keepalive and clean interruption. Current boot has no kernel OOM entries; OOM remains unproved.
- Windows has WSL 3.0.1 / Linux 6.18.40.1; Docker lives inside Ubuntu-24.04.
- Existing launchers assume Windows Docker and fail to check native exit codes.
- Instructions include a main-tree pytest launcher inside a worktree and staging examples using production port 18000.
- PG-only fixtures can skip when no allowed admin DSN connects; exit zero does not establish PostgreSQL proof.
- Existing shared and T07 Compose projects must be preserved.

## Checkpoint

- Native WSL entry point complete: Preflight / Check / Start / Stop / Session. Session owns an EOF-based keeper for the full child lifetime and releases it in finally.
- Explicit Compose project, ignored env, canonical YAML and `ops/` relative path base; fixed local daemon socket; no ambient Compose overrides. Protect source mounts, foreign projects, production ports and native Windows listener ownership.
- Strict PostgreSQL mode is intentionally limited to the audited effective-settings suite / `RQ23A_PG_ADMIN_URL`. It constructs the command, pins candidates against dotenv fallback, normalizes only app DATABASE_URL to psycopg, and requires a new zero-skip report. Other fixtures require a separate routing audit (RQ15D has a hardcoded fallback).
- Next exact action: inspect #3559 exact-head CI/review and fix blocking failures in this branch. Initial checks are pending; skipped jobs are not passes. Do not resume T08 or alter #3557 as part of this tooling PR.
- Shared projects and global WSL settings preserved. No application/deployment verification claim.

## Validation — 2026-10-02, Asia/Tashkent

Environment: Windows PowerShell, Python 3.11.9, WSL 3.0.1.0 / Ubuntu-24.04, Docker 29.1.3 / Compose 2.40.3. Worktree patch based on `9a5404a5`; exact published HEAD is recorded in the PR.

| Check | Result | Evidence |
|---|---|---|
| Host tooling regressions | PASS | `scripts/run_python.ps1 -PythonArgs @('-m','pytest','scripts/tests/test_wsl_staging_guard.py','-q','--junitxml=output/staging/wsl-tooling-tests.xml')`: 91 passed, 0 skipped; includes mocked actual PowerShell wrapper argv/exit tests |
| Canonical local PG DSN guard | PASS | Worktree `scripts/run_backend_pytest.ps1 tests/integration/test_pg_admin_local_guard.py --confcutdir=tests/integration -q`: 192 passed; pure admission tests, no PostgreSQL connection or schema proof |
| Black / Ruff | PASS | Check mode on the two new Python files |
| Whitespace/scope | PASS | `git diff --check`; no runtime, Compose YAML, auth, migration or other worktree changes |
| Real Preflight | PASS | Own ignored synthetic configuration, unique project and ports 18003/18083/55435; no Compose services created. JSON explicitly has runtime_readiness NOT_RUN and served_revision_verified false |
| Real keeper lifetime | PASS | Owned local probe held the keeper for 75 seconds, equal before/after boot ID, keeper alive through the interval and released after scope exit |
| Code review | PASS | Read-only independent review: P0=0/P1=0/P2=0 after closing PG fallback, driver and Windows listener findings |
| Real full-stack Start/Stop and strict PG command | NOT_RUN | No additional application stack built; existing shared/T07 projects were preserved. Command flow, failure abort, scope and skip handling covered by mocks |
| Full application staging checklist | NOT_RUN | Sentry, DR restore, AI flag, AI safety E2E, arq, Telegram, PII pipeline, installed hooks, full backend suite, full frontend build/unit checks not executed for this tooling slice |

Original failures and corrections:

- Native preflight initially rejected source: helper's project-directory incorrectly pointed at repo root. Corrected to `ops/`, matching canonical YAML relative paths, and reran successfully; regression test pins the path.
- Standard canonical-guard invocation initially hit app conftest with no DATABASE_URL. Reran the pure DSN suite with `--confcutdir=tests/integration`; did not invent a production/test DB or install packages into production venv.
- Review found alternative PostgreSQL candidates could escape the selected port; child candidates are now explicitly pinned/blanked. A suite with a hardcoded fallback is excluded from the supported strict path.
- Review found Windows TCP readiness alone could accept a native foreign listener; owner checks now reject that case before dependent tests.

Limitations: helper HEAD/mount/image metadata identifies the selected source surface but does not prove a baked frontend image serves that commit; `served_revision_verified=false` is deliberate. Admin browser checks still require normal synthetic 2FA setup. No cause is attributed to OOM without kernel evidence.
