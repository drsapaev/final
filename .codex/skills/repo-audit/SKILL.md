---
name: repo-audit
description: Audit repository state, stack, workflows, and setup constraints in drsapaev/final before planning or execution work. Use when starting a bounded task or validating current repo status.
argument-hint: "[scope or focus]"
---

# repo-audit

## Goal

- Build a current-state snapshot of repo structure, tooling, workflows, and execution risks.

## Inputs

- Optional focus area such as `backend`, `frontend`, `ci`, or `docs`.

## Constraints

- No broad refactors.
- No claims of completion without file or command evidence.
- Treat auth, payments, queue, EMR, alembic, secrets, and workflow permissions as protected zones.

## Workflow

1. Inspect git state, repo layout, and existing AI metadata.
2. Read stack-defining files and workflow files.
3. Check local tooling availability and obvious reproducibility blockers.
4. Record what exists, what is missing, and what should stay protected.

## Verification

- Confirm findings against repo files and local commands.
- Prefer direct file references over narrative assumptions.

## Expected Artifacts

- A status note or `docs/status/*.md` precheck report with blockers and protected zones.
