# WSL staging sessions

Use `ops/scripts/wsl_staging.ps1` from the worktree containing the commit under
test. It is the Windows entrypoint for the Docker daemon inside
`Ubuntu-24.04`; Docker Desktop is not required. The launcher fixes the Compose
file and local Docker socket, checks the selected project's isolation, and
returns a compact JSON result with a nonzero exit code on failure.

This is an environment and test-session check. It does not complete the ten
checks in [STAGING_VALIDATION.md](STAGING_VALIDATION.md).

## First use in a worktree

1. Read the task's current evidence and checkpoint before creating anything.
2. Use an ignored env file inside your own worktree. Create synthetic secrets
   and users; never copy production data or credentials.
3. Set an explicit, unique `COMPOSE_PROJECT_NAME`, plus
   `STAGING_BACKEND_PORT`, `STAGING_FRONTEND_PORT`, and
   `STAGING_POSTGRES_HOST_PORT`. Choose free ports. Do not take ports from an
   existing staging project just because its worktree belongs to an older PR.
4. Run the launcher before building or writing fixtures:

```powershell
cd C:\final\_wt_<topic>
.\ops\scripts\wsl_staging.ps1 -Action Preflight -EnvFile ops/staging.env
```

Use the returned reason to resolve a failed prerequisite once. Do not repeat
the build or test command while that prerequisite still fails. `Preflight`
may boot the selected WSL distribution. It validates config, identity, ports,
and the distribution without starting Compose services; runtime readiness is
`NOT_RUN`. Use `Check` after startup when the complete healthy stack is
required.

Start your own stack:

```powershell
.\ops\scripts\wsl_staging.ps1 -Action Start -EnvFile ops/staging.env -TimeoutSec 180
```

For an already-built stack, add `-NoBuild`. Native Docker failures are not
successful starts. Check Windows connectivity as well as container health:
the returned checks distinguish a healthy Linux service from a port that
Windows cannot reach.

The launcher rejects protected host ports `18000`, `5173`, and `5432`, foreign
project conflicts, source mounts from a different worktree, and foreign or
ambiguous Windows listeners even when Docker also publishes that port.
Container health and source mount identity are not proof of the revision
baked into a frontend image. The helper reports image IDs, `worktree_dirty`,
and `served_revision_verified=false`. Record those facts with the worktree
HEAD and project/mount/boot identity; obtain separate build provenance before
claiming the served frontend matches an exact commit.

## Keep one session alive for the whole validation

`Start` holds WSL alive only while startup is running. Once your stack is
started, wrap the entire long test or browser validation in `Session`:

```powershell
$validationScript = Join-Path (Get-Location) 'output/staging/validate-own-session.ps1'
.\ops\scripts\wsl_staging.ps1 -Action Session -EnvFile ops/staging.env `
  -CommandArgs @('powershell.exe', '-NoProfile', '-File', $validationScript)
```

The validation script is task-owned and ignored, stays inside the worktree,
and must propagate failed command exit codes. Put backend tests, browser
checks, and their evidence collection in that script. The keeper lives for
the invocation and is released when the validation ends; it does not rely on
a `sleep 1800` timer. Do not launch a short-lived keeper in one command and
assume a later independent command is protected.

Run browser work during this session. Normal synthetic Admin login may
require 2FA enrollment before an Admin screen can be tested. Prepare that
account through the normal flow; do not bypass authentication. Missing login
or enrollment makes the dependent browser checks `NOT_RUN`.

To stop only your configured project:

```powershell
.\ops\scripts\wsl_staging.ps1 -Action Stop -EnvFile ops/staging.env
```

Do not use `wsl --shutdown`, change global `.wslconfig`, stop another project,
or invoke the legacy `start_staging_host.ps1`/`stop_staging_host.ps1` as a
fallback. Other agents can be running in the same distribution, and legacy
host staging can collide with Windows production on `:18000`.

## PostgreSQL-required tests

SQLite unit tests do not prove PostgreSQL behavior. Before running a
PostgreSQL-required suite, audit the fixture's connection routing. The helper
currently supports only `RQ23A_PG_ADMIN_URL` and the fixed effective-settings
suite `backend/tests/integration/test_effective_queue_settings_report.py`.
Set that variable privately to a raw `postgresql://` local admin URI using
this project's PostgreSQL port. Do not print it or put it in a committed
script.

Use a disposable test database with the fixture's required name/confirmation
guards. Never run destructive fixtures in the shared staging database. If a
fixture needs a separate PostgreSQL project, give it its own env file and
ports and validate that project independently.

Run the supported suite with a fresh, unique absolute JUnit report:

```powershell
$junit = Join-Path (Get-Location) ('output/staging/pg-' + [guid]::NewGuid().ToString('N') + '.xml')
# Set RQ23A_PG_ADMIN_URL privately before this command.
.\ops\scripts\wsl_staging.ps1 -Action Session -EnvFile ops/staging.env `
  -PgAdminEnv RQ23A_PG_ADMIN_URL -Junit $junit
```

The helper runs that audited suite automatically. `-CommandArgs` and other
PG environment-variable names are rejected in strict PG mode. It pins the
chosen DSN in the child environment, normalizes child `DATABASE_URL` to
`postgresql+psycopg://`, and blanks alternate fallback DSNs/passwords so a
dotenv load cannot restore another destination. Parent variables are unchanged.

`-Junit` requires fresh results with no skipped tests. A missing DB, timeout,
fallback to `localhost:5432`, or a skipped PostgreSQL case cannot be recorded
as PostgreSQL validation success. Other PG suites require a separate fixture
routing audit and are not covered by this helper's proof; for example,
`RQ15D` fixtures have a hardcoded `55432` destination that this environment
guard cannot override.

Use the backend launcher from the worktree, even when reusing an interpreter:

```powershell
$env:REPO_PYTHON = 'C:\final\backend\.venv\Scripts\python.exe'
$junit = Join-Path (Get-Location) ('output/staging/unit-' + [guid]::NewGuid().ToString('N') + '.xml')
.\scripts\run_backend_pytest.ps1 tests\<target>.py "--junitxml=$junit"
```

The absolute report path is essential: the backend launcher runs pytest from
`backend/`, while the helper resolves reports from the worktree root.

If invoking `run_python.ps1` directly, name the argument parameter:
`-PythonArgs @('path/to/script.py', 'argument')`. A positional script path can
bind to `RequireModule` instead.

## Repeated failures and the next action

| Symptom | Check first | Action |
|---|---|---|
| Every container has a new uptime after an idle period | Helper boot identity and the previous session lifetime | Use one `Session` for the complete validation. Record a changed boot identity; do not infer an OOM crash from uptime alone. |
| Wrong Compose file or duplicate YAML key | Invocation used the canonical helper | Use the fixed `ops/compose.staging.yml`; do not run bare `docker compose up` in `ops/`. |
| Linux mount/path changes when launched from Windows | Shell used for Docker invocation | Use native PowerShell to call the helper, which invokes `wsl.exe`; do not route it through Git Bash/MSYS path conversion. |
| Address in use or another PR's rows appear | Explicit project, host ports, source mount | Keep the foreign project running and choose separate project/ports. |
| Linux health is good but Windows cannot connect | Helper Windows TCP checks | Treat forwarding as a failed prerequisite; do not turn failed PostgreSQL tests into skips and keep running. |
| Scratch PostgreSQL disappears before logs can be inspected | Container lifetime and ownership | Preserve the task-owned container until diagnosis is recorded; avoid disposable `--rm` processes during failure investigation. |
| Build stops on a small Windows host | Host disk/RAM and recorded native error | Free task-owned artifacts safely or reduce simultaneous task-owned builds. Diagnose the failure before another build; do not delete foreign images/volumes. |
| Browser reaches login instead of the Admin screen | Synthetic account's normal 2FA state | Finish normal enrollment or record browser checks `NOT_RUN`. |

The user's October 2026 staging report described expired temporary keepalive,
wrong Compose selection, MSYS path conversion, port conflicts, and unavailable
PostgreSQL. These are the reported failure patterns this entrypoint addresses;
they are not all independently reproduced defects. Kernel OOM was not
confirmed. Low host RAM/disk space is a resource constraint, not proof that an
earlier restart was caused by OOM. Capture bounded kernel evidence before
assigning that cause.

## Durable evidence

Keep the latest compact result and exact next action in the task checkpoint:
commit under test, worktree, project, ports, boot identity, invocation,
`PASS`/`FAIL`/`NOT_RUN`, fresh report path, and any remaining prerequisite.
Record failed and skipped checks honestly. Do not publish env files, resolved
Compose configuration, raw logs, tokens, patient data, or complete network
payloads. A future agent should use that checkpoint and rerun only the failed
prerequisite or checks affected by a new change.
