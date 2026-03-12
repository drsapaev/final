# OpenHands Local Runbook

Date: 2026-03-06

## Purpose

Run OpenHands locally as the execution layer for bounded repo work without pretending that full AI Factory automation already exists.

## Current Status

- Repo-local wrapper added: yes
- Full local launch validated in this session: no
- Reason: Docker daemon was not reachable and no LLM credentials were configured

## Why This Runbook Uses Docker/WSL

The official OpenHands docs currently point to:

- Docker GUI setup for local use
- local CLI commands that expect Python `3.12+`
- headless mode that runs in always-approve mode

Local precheck found:

- Python `3.11.1`
- no `uv`
- Docker CLI and Compose installed
- WSL present

That makes Docker GUI the least risky and most reproducible starting point for this repo.

Official references used while preparing this runbook:

- `https://docs.openhands.dev/usage/getting-started/local-setup-gui`
- `https://docs.openhands.dev/usage/commands`

## Repo-Local Files

- `ops/openhands/docker-compose.yml`
- `ops/openhands/start-openhands.ps1`
- `ops/openhands/stop-openhands.ps1`
- `ops/openhands/render-contract.ps1`

## Prerequisites

1. Start Docker Desktop and confirm the Linux engine is running.
2. Ensure WSL integration is available for the distro you want to use.
3. Prepare the LLM/provider configuration that OpenHands itself needs.
4. Keep the repo on a feature branch or local working branch for execution work.

## Start OpenHands

From PowerShell:

```powershell
pwsh -File .\ops\openhands\start-openhands.ps1
```

If your Docker-enabled WSL distro is not the default:

```powershell
pwsh -File .\ops\openhands\start-openhands.ps1 -Distro Ubuntu
```

The script:

- converts repo and state paths to WSL format
- exports the workspace mount as `/workspace`
- starts the repo-local compose file
- exposes OpenHands at `http://localhost:3000`

## Stop OpenHands

```powershell
pwsh -File .\ops\openhands\stop-openhands.ps1
```

## Prepare A Contract Handoff

Render a contract JSON file into a prompt file:

```powershell
pwsh -File .\ops\openhands\render-contract.ps1 `
  -ContractPath .\.ai-factory\contracts\verify-docs-vs-code.contract.json
```

The renderer writes a sibling `*.handoff.md` file by default.

## Recommended Usage Pattern

1. Fill or update a contract template in `.ai-factory/contracts/`.
2. Human reviews scope, protected paths, and budgets.
3. Render the handoff prompt.
4. Start OpenHands locally.
5. Paste or load the rendered prompt into the OpenHands session.
6. Keep execution bounded to the contract.
7. Review local results and then rely on GitHub Actions as arbiter.

## What Not To Do

- Do not run protected-domain work without human review.
- Do not treat headless mode as the default path for this repo.
- Do not push directly to `main`.
- Do not pass production secrets into the container as part of this setup.

## Troubleshooting

### Docker daemon not reachable

Symptom:

- `docker info` fails

Action:

- start Docker Desktop
- verify WSL integration is enabled
- re-run the start script

### Wrong WSL distro

Symptom:

- Docker works in one distro but not from the script

Action:

- rerun with `-Distro <name>`

### Port `3000` already in use

Action:

- free the port or modify `OPENHANDS_PORT` inside the start script command block before launch

### Workspace path issues

Action:

- confirm the repo is on a local drive path that can be converted to `/mnt/<drive>/...`

## Ready / Partial / Pending

- Ready: repo-local launcher, stop script, compose wrapper, contract renderer
- Partial: local run validation, because the daemon was unavailable during setup
- Pending: any fully automated planner-to-executor handshake beyond contract files and manual approval
