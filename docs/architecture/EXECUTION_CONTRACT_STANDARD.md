# Execution Contract Standard

Date: 2026-03-06

## Purpose

Execution contracts are the handoff boundary between AI Factory planning and OpenHands execution.

All contract templates live in:

- `.ai-factory/contracts/`

## Format

Contracts use JSON so they can be:

- reviewed by humans
- validated by simple scripts
- rendered into OpenHands prompts

## Required Fields

Every contract must include:

- `task_type`
- `repo`
- `scope.include`
- `scope.exclude`
- `goals`
- `constraints`
- `must_run`
- `must_not_touch`
- `required_artifacts`
- `stop_conditions`
- `review_notes`

## Required Constraint Defaults

Each contract must enforce these defaults unless a human explicitly overrides them:

- PR-only mode
- no direct push to `main`
- `max_files_changed`
- `max_diff_lines`
- tests must run
- protected paths listed explicitly
- mandatory human review for auth, payments, queue, EMR, or migration-sensitive work

## Standard Constraint Shape

```json
{
  "constraints": {
    "execution_mode": "pr-only",
    "no_direct_push_to_main": true,
    "max_files_changed": 10,
    "max_diff_lines": 400,
    "must_run_tests": true,
    "mandatory_human_review": false,
    "protected_paths": [
      "backend/alembic/**",
      ".github/workflows/**"
    ]
  }
}
```

## Template Catalog

The foundation includes starter contracts for:

- `polish-core`
- `boost-tests`
- `refactor-module`
- `verify-docs-vs-code`
- `stabilize-ci`
- `audit-rbac`
- `audit-contracts`
- `audit-queue`
- `harden-payments`
- `polish-accessibility`
- `cleanup-docs`

These are starter templates, not final task requests. Each one must be filled in for the concrete task before execution.

## Review Rules

Before execution:

1. confirm the task type matches the requested work
2. confirm protected paths are excluded or explicitly escalated
3. confirm the file and diff budgets are realistic
4. confirm the `must_run` checks are actionable
5. confirm artifacts describe what the executor must return

## Stop Rules

Execution must stop when:

- protected paths must be changed unexpectedly
- the contract budget will be exceeded
- required checks cannot run
- secrets or production credentials would be needed
- the requested change no longer matches the contract

## Renderer Support

Use the repo-local renderer to convert a filled contract into an OpenHands handoff prompt:

```powershell
pwsh -File .\ops\openhands\render-contract.ps1 `
  -ContractPath .\.ai-factory\contracts\<task>.contract.json
```

## Policy Note

The contract is the execution boundary. If the work falls outside the contract, the correct behavior is to stop and ask for a revised contract, not to continue creatively.
