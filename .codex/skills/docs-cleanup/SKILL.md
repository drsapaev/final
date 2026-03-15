---
name: docs-cleanup
description: Clean up stale or duplicated documentation in drsapaev/final while preserving accuracy. Use when documentation needs tighter navigation, fewer optimistic claims, or better setup/runbook clarity.
argument-hint: "[doc area]"
---

# docs-cleanup

## Goal

- Make repo documentation more accurate, less duplicated, and easier to navigate.

## Inputs

- A doc path, topic area, or a list of stale claims to verify.

## Constraints

- Prefer documentation changes over code changes.
- Remove or downgrade unverified success language.
- Stop if the cleanup requires protected code changes.

## Workflow

1. Identify duplicated, stale, or misleading documentation.
2. Verify claims against code and tests where possible.
3. Consolidate or update docs without over-claiming status.
4. Keep navigation and runbook links coherent.

## Verification

- Re-check changed links and the nearest relevant verification command for any factual claim.

## Expected Artifacts

- Updated docs, list of downgraded or removed claims, and verification notes.
