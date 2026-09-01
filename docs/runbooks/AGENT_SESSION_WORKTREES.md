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
$env:REPO_PYTHON = 'C:\final\backend\.venv\Scripts\python.exe'
C:\final\scripts\run_backend_pytest.ps1 tests\test_something.py
```

Alternatively, junction the venv into the worktree (read-write — installs
affect production, so prefer `REPO_PYTHON`):

```powershell
cmd /c mklink /J C:\final\_wt_<topic>\backend\.venv C:\final\backend\.venv
```

Frontend checks: junction `frontend\node_modules` the same way, or run
them in the main tree only when it is parked on `main` (CI covers PRs
anyway).

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
