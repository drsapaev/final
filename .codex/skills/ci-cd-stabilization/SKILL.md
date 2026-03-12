---
name: ci-cd-stabilization
description: Stabilize one failing or flaky CI path in drsapaev/final with the smallest reproducible fix. Use for GitHub Actions or repo-local CI support files.
argument-hint: "[workflow or job name]"
---

# ci-cd-stabilization

## Goal

- Fix a concrete CI failure without widening scope into workflow redesign.

## Inputs

- Workflow name, job name, failing command, or log excerpt.

## Constraints

- Human review is mandatory for workflow edits.
- No secret changes.
- No permission escalation without explicit approval.

## Workflow

1. Reproduce or approximate the failing step locally.
2. Identify the narrowest repo-owned fix.
3. Update only the workflow or support files needed for that failure.
4. Document the failure cause and the proof of fix.

## Verification

- Re-run the failing command locally or through the closest narrow equivalent.

## Expected Artifacts

- Failure summary, fix summary, and local verification notes.
