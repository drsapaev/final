# Agent Session Worktrees & Production Deploy

Operational mechanics for the **Multi-Session Worktree & Deploy Convention**
(see `AGENTS.md`). This host runs production (uvicorn :18000 → Cloudflare
Tunnel) from the same checkout agents work in, so the main tree is a
deploy surface, not a workspace.

## Rules (short form)

1. Production deploys only from the main tree (`C:\final`) on `main`,
   clean and synced with `origin/main`.
2. Sessions work in their own worktree; never switch branches in the
   main tree.
3. The main tree returns to `main` only after your own PR is merged.

## Isolated Linux staging on this host

The separate test environment runs in WSL2 Ubuntu 24.04 with Docker Compose
on this same Windows computer; it is not a VPS. Its executable configuration
is `ops/compose.staging.yml`. Run it from the worktree containing the commit
under test, not from an old staging worktree snapshot. The Compose project,
Postgres/Redis volumes, database credentials, and host ports must be separate
from production. Staging can be stopped between tests; check its state first
using the worktree's Windows-to-WSL launcher:

```powershell
.\ops\scripts\wsl_staging.ps1 -Action Preflight -EnvFile ops/staging.env
.\ops\scripts\wsl_staging.ps1 -Action Start -EnvFile ops/staging.env
```

Set an explicit unique `COMPOSE_PROJECT_NAME` in that ignored env file.
`Preflight` checks prerequisites before the first build and reports runtime
readiness `NOT_RUN`; use `Check` for an already-started healthy stack.
Use `-Action Session -CommandArgs @(...)` around the complete long-running
test/browser script, so the WSL keeper lasts until validation ends rather
than expiring after a fixed sleep. `Start` holds the keeper only during
startup. Stop only your project with `-Action Stop`. Full recipes, strict
PostgreSQL result checks, and recurring failure handling are in
[WSL_STAGING_SESSION.md](WSL_STAGING_SESSION.md). Do not shut down the shared
distribution or fall back to legacy host staging on production's port.

### Staging lifecycle contract (mandatory)

Every Compose project started from `ops/compose.staging.yml` is an
**ephemeral test environment**, not a deployment. The historical failure
mode this prevents: creation is automated and per-PR isolated, but
teardown was optional, so forgotten stacks accumulated (containers +
volumes + ~2.4 GB of project images per run), re-occupied the standard
18001/18080/55432 contour through `restart: unless-stopped`, and blocked
the next validation session. The contract:

1. **Create** with a unique `COMPOSE_PROJECT_NAME` and the lifecycle
   labels (`CLINIC_OWNER`, `CLINIC_EXPIRES_AT`) from the compose file.
   `CLINIC_EXPIRES_AT` is an ISO timestamp (e.g. now + 2 days) used by GC.
2. **Validate.** If a failure needs the live stack preserved, set
   `KEEP_STAGING=1` and record it in the task checkpoint; this is the
   ONLY accepted reason to leave a stack running.
3. **Teardown is mandatory** at the end of every run — a normal
   successful validation always ends with:

   ```powershell
   powershell -File scripts/staging_down.ps1 -ProjectName <name> [-EnvFile ops/staging.env]
   ```

   This runs `docker compose down -v --remove-orphans --rmi local`
   (containers, networks, named volumes, locally built images) and refuses
   to run while `KEEP_STAGING=1` is set unless `-Force` is passed.
4. **Disposable test containers** (scratch PostgreSQL for PG-backed tests)
   always run with `--rm`, or are removed in the test's own teardown.
5. **Session-start/end GC** sweeps forgotten leftovers — it removes ONLY
   resources labeled `clinic.lifecycle=ephemeral` whose
   `clinic.expires_at` has passed; unlabeled resources are never touched,
   and there is deliberately no global `docker system prune`:

   ```powershell
   powershell -File scripts/staging_gc.ps1 -DryRun   # list
   powershell -File scripts/staging_gc.ps1           # remove expired
   ```

   A stack with no `CLINIC_EXPIRES_AT` is report-only (KEEP) — set the
   label when starting a stack so GC can eventually reclaim it.

Both scripts detect whether `docker.exe` exists on Windows PATH and
otherwise wrap `wsl -d Ubuntu-24.04 -- docker`, converting paths.

Current local staging uses backend `127.0.0.1:18001`, frontend
`127.0.0.1:18080`, and Postgres `127.0.0.1:55432`. Windows production uses
backend `:18000`. Set `STAGING_BACKEND_PORT=18001` (or another free port)
and `STAGING_POSTGRES_HOST_PORT=55432` explicitly in the untracked staging
env file before starting Compose. The sample and Compose backend fallback
now both use `18001`; the sample Postgres port is `15432`, while the current
local staging contour uses `55432`. Check the effective project name and
port bindings with the helper's compact result, then check staging backend health at
`http://127.0.0.1:18001/api/v1/health`. Do not print the env file or
interpolated Compose configuration into logs because it contains secrets.
Postgres is loopback-bound; the current Compose file publishes backend and
frontend host ports on all interfaces, so verify intended LAN access.

Use synthetic staging fixtures only. Never restore or copy production
patient data into this environment. Role-by-role checks live in
`docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md`; the full pre-deploy
checklist remains `docs/runbooks/STAGING_VALIDATION.md`.

## Session worktree setup

```powershell
cd C:\final
git worktree add C:\final\_wt_<topic> -b <branch> origin/main
cd C:\final\_wt_<topic>
```

- Branch name follows the PR convention (`fix/...`, `perf/...`, `docs/...`).
- `_wt*/` is gitignored; scratch files (profiles, dumps, PR bodies) stay
  inside your worktree.

## Running backend tests from a worktree

The worktree has no `.venv`. Point the launchers at the main tree's
interpreter (same app, same dependency set):

```powershell
cd C:\final\_wt_<topic>
$env:REPO_PYTHON = 'C:\final\backend\.venv\Scripts\python.exe'
.\scripts\run_backend_pytest.ps1 tests\test_something.py
```

Alternatively, junction the venv into the worktree (read-write — installs
affect production, so prefer `REPO_PYTHON`):

```powershell
cmd /c mklink /J C:\final\_wt_<topic>\backend\.venv C:\final\backend\.venv
```

The launcher derives the repository root from its own path: always use the
worktree's script, even when reusing the main tree's interpreter. Do not
install packages into the production venv. PostgreSQL-required tests need an
explicit isolated DSN and fresh results with no skipped cases. The helper's
strict `Session -PgAdminEnv RQ23A_PG_ADMIN_URL -Junit <absolute-path>` mode runs
only its audited effective-settings suite. Other fixtures need separate
connection-routing audit; see `WSL_STAGING_SESSION.md`.

Frontend checks: junction `frontend\node_modules` the same way if dependencies
match, or install dependencies in the worktree. Run checks from the worktree.

## PR flow from a worktree

Standard cyclic workflow (`AGENT_CYCLIC_WORKFLOW.md`): branch from fresh
`origin/main`, small scope, evidence in the PR body, green CI, merge.
Squash-merge is the repo default.

## Returning the main tree to main (after your merge)

Only when no other session is mid-operation (ask / check for open
editors and running processes):

```powershell
cd C:\final
git status --porcelain          # must be empty for tracked files
git switch main
git pull --ff-only origin main
```

If the tree is dirty with another session's work — stop; that session
owns the tree until it finishes.

## Production deploy / restart

Always through the guard script (refuses to deploy anything but merged
`main` from a clean synced main tree):

```powershell
C:\final\scripts\deploy_restart.ps1 -CheckOnly   # guards only, no restart
C:\final\scripts\deploy_restart.ps1              # guarded restart + health poll
```

The script: verifies branch == `main`, clean tracked tree, HEAD ==
`origin/main` (fast-forwards when behind), stops the uvicorn process
tree on :18000, starts a detached uvicorn from `backend\.venv`
(`Start-Process`, minimized — survives the launching session), then
polls `/api/v1/health` until OK (90s budget).

Deploy window: after clinic hours (~18:00+) unless the operator says
otherwise. A restart drops active sessions — doctors/cashiers get kicked
to login.

## Historical note

Before this convention (2026-09-01) two sessions shared the main tree:
branch switches under a live session caused phantom file reverts, a PR
branch carried another session's feature commits, and a restart could
have deployed an unmerged feature branch. The worktree rule exists
because of that afternoon.
